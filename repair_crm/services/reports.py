from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from models import Order, PrintJob, Filament, FilamentMovement, OrderItem, OrderPart, Part, StockMovement
from models import Client, Service
from config import TIMEZONE_OFFSET


class ReportsService:
    @staticmethod
    def generate_monthly_report(session: Session, year: int, month: int) -> Dict[str, Any]:
        """Генерирует полный месячный отчёт"""
        local_start = datetime(year, month, 1)
        if month == 12:
            local_end = datetime(year + 1, 1, 1)
        else:
            local_end = datetime(year, month + 1, 1)
        
        start_date_created = local_start - TIMEZONE_OFFSET
        end_date_created = local_end - TIMEZONE_OFFSET
        
        start_date_closed = local_start
        end_date_closed = local_end
        
        report = {
            "period": {
                "year": year,
                "month": month,
                "month_name": ReportsService._get_month_name(month),
                "start_date": local_start.strftime("%d.%m.%Y"),
                "end_date": (local_end - timedelta(days=1)).strftime("%d.%m.%Y")
            },
            "orders": ReportsService._get_orders_stats(session, start_date_created, end_date_created, start_date_closed, end_date_closed),
            "prints": ReportsService._get_prints_stats(session, start_date_created, end_date_created),
            "filaments": ReportsService._get_filaments_stats(session, start_date_created, end_date_created),
            "services": ReportsService._get_services_stats(session, start_date_created, end_date_created, start_date_closed, end_date_closed),
            "parts": ReportsService._get_parts_stats(session, start_date_created, end_date_created),
            "clients": ReportsService._get_clients_stats(session, start_date_created, end_date_created, start_date_closed, end_date_closed),
            "revenue": ReportsService._get_revenue_stats(session, start_date_closed, end_date_closed)
        }
        
        return report
    
    @staticmethod
    def _get_orders_stats(session: Session, start_created: datetime, end_created: datetime, start_closed: datetime, end_closed: datetime) -> Dict[str, Any]:
        created_orders = session.query(Order).filter(
            and_(
                Order.created_at >= start_created,
                Order.created_at < end_created
            )
        ).all()
        
        closed_orders = session.query(Order).filter(
            and_(
                Order.status == 'closed',
                Order.closed_at >= start_closed,
                Order.closed_at < end_closed
            )
        ).all()
        
        total_created = len(created_orders)
        total_closed = len(closed_orders)
        
        total_revenue = sum(o.total_price or 0 for o in closed_orders)
        avg_check = total_revenue / total_closed if total_closed > 0 else 0
        
        created_by_type = {
            'repair': len([o for o in created_orders if o.order_type == 'repair']),
            'print': len([o for o in created_orders if o.order_type == 'print'])
        }
        
        closed_by_type = {
            'repair': len([o for o in closed_orders if o.order_type == 'repair']),
            'print': len([o for o in closed_orders if o.order_type == 'print'])
        }
        
        status_counts = {}
        for order in created_orders:
            status = order.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total": total_created,
            "created": total_created,
            "completed": total_closed,
            "total_revenue": total_revenue,
            "avg_check": round(avg_check, 2),
            "by_type": created_by_type,
            "closed_by_type": closed_by_type,
            "by_status": status_counts
        }
    
    @staticmethod
    def _get_prints_stats(session: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        jobs = session.query(PrintJob).filter(
            and_(
                PrintJob.created_at >= start_date,
                PrintJob.created_at < end_date,
                PrintJob.status != 'pending'
            )
        ).all()
        
        total_jobs = len(jobs)
        successful_jobs = len([j for j in jobs if j.status == 'success'])
        failed_jobs = len([j for j in jobs if j.status == 'fail'])
        
        total_grams = sum(j.grams or 0 for j in jobs)
        total_hours = sum(j.hours or 0 for j in jobs)
        
        # Расход пластика по типам
        filament_usage = {}
        for job in jobs:
            if job.filament:
                filament_type = job.filament.type or 'Неизвестно'
                filament_usage[filament_type] = filament_usage.get(filament_type, 0) + (job.grams or 0)
        
        # Топ принтеров
        printer_usage = {}
        for job in jobs:
            printer = job.printer_name or 'Неизвестно'
            printer_usage[printer] = printer_usage.get(printer, 0) + 1
        
        return {
            "total_jobs": total_jobs,
            "successful": successful_jobs,
            "failed": failed_jobs,
            "success_rate": round((successful_jobs / total_jobs * 100), 1) if total_jobs > 0 else 0,
            "total_grams": total_grams,
            "total_hours": round(total_hours, 1),
            "filament_usage": filament_usage,
            "printer_usage": printer_usage
        }
    
    @staticmethod
    def _get_filaments_stats(session: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Статистика по пластику"""
        movements = session.query(FilamentMovement).filter(
            and_(
                FilamentMovement.created_at >= start_date,
                FilamentMovement.created_at < end_date
            )
        ).all()
        
        income = sum(m.quantity for m in movements if m.type == 'in')
        expense = sum(m.quantity for m in movements if m.type == 'out')
        
        # По типам пластика
        by_type = {}
        for movement in movements:
            if movement.filament:
                filament_type = movement.filament.type or 'Неизвестно'
                if filament_type not in by_type:
                    by_type[filament_type] = {"in": 0, "out": 0}
                by_type[filament_type][movement.type] += movement.quantity
        
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "by_type": by_type
        }
    
    @staticmethod
    def _get_services_stats(session: Session, start_created: datetime, end_created: datetime, start_closed: datetime, end_closed: datetime) -> Dict[str, Any]:
        """Статистика по услугам (из закрытых заказов)"""
        items = session.query(OrderItem).join(Order).filter(
            and_(
                Order.status == 'closed',
                Order.closed_at >= start_closed,
                Order.closed_at < end_closed
            )
        ).all()
        
        service_stats = {}
        for item in items:
            name = item.name
            if name not in service_stats:
                service_stats[name] = {"count": 0, "total": 0}
            service_stats[name]["count"] += 1
            service_stats[name]["total"] += item.price or 0
        
        top_services = sorted(
            [{"name": k, "count": v["count"], "total": v["total"]} for k, v in service_stats.items()],
            key=lambda x: x["total"],
            reverse=True
        )[:5]
        
        return {
            "total_services_sold": len(items),
            "total_revenue": sum(item.price or 0 for item in items),
            "top_services": top_services
        }
    
    @staticmethod
    def _get_parts_stats(session: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Статистика по запчастям"""
        movements = session.query(StockMovement).filter(
            and_(
                StockMovement.created_at >= start_date,
                StockMovement.created_at < end_date
            )
        ).all()
        
        income = sum(m.quantity for m in movements if m.type == 'in')
        expense = sum(m.quantity for m in movements if m.type == 'out')
        
        # Топ запчастей по расходу
        parts_usage = {}
        for movement in movements:
            if movement.type == 'out' and movement.part:
                part_name = movement.part.name
                parts_usage[part_name] = parts_usage.get(part_name, 0) + movement.quantity
        
        top_parts = sorted(
            [{"name": k, "quantity": v} for k, v in parts_usage.items()],
            key=lambda x: x["quantity"],
            reverse=True
        )[:5]
        
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "top_parts": top_parts
        }
    
    @staticmethod
    def _get_clients_stats(session: Session, start_created: datetime, end_created: datetime, start_closed: datetime, end_closed: datetime) -> Dict[str, Any]:
        all_orders = session.query(Order).filter(
            and_(
                Order.created_at >= start_created,
                Order.created_at < end_created
            )
        ).all()
        
        unique_clients = len(set(o.client_id for o in all_orders if o.client_id))
        
        new_clients = session.query(Client).filter(
            and_(
                Client.created_at >= start_created,
                Client.created_at < end_created
            )
        ).count()
        
        return {
            "unique_clients": unique_clients,
            "new_clients": new_clients,
            "total_orders": len(closed_orders)
        }
    
    @staticmethod
    def _get_revenue_stats(session: Session, start_closed: datetime, end_closed: datetime) -> Dict[str, Any]:
        """Статистика по выручке (по дате закрытия заказа)"""
        closed_orders = session.query(Order).filter(
            and_(
                Order.status == 'closed',
                Order.closed_at >= start_closed,
                Order.closed_at < end_closed
            )
        ).all()
        
        order_ids = [o.id for o in closed_orders]
        
        total_revenue = sum(o.total_price or 0 for o in closed_orders)
        
        repair_revenue = sum(o.total_price or 0 for o in closed_orders if o.order_type == 'repair')
        print_revenue = sum(o.total_price or 0 for o in closed_orders if o.order_type == 'print')
        
        parts_cost = 0
        if order_ids:
            order_parts = session.query(OrderPart).filter(
                OrderPart.order_id.in_(order_ids)
            ).all()
            
            for op in order_parts:
                parts_cost += (op.price or 0) * op.quantity
        
        profit = total_revenue - parts_cost
        
        return {
            "total": total_revenue,
            "parts_cost": parts_cost,
            "profit": profit,
            "by_type": {
                "repair": repair_revenue,
                "print": print_revenue
            }
        }
    
    @staticmethod
    def _get_month_name(month: int) -> str:
        """Возвращает название месяца на русском"""
        months = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        return months[month - 1] if 1 <= month <= 12 else "Неизвестно"
    
    @staticmethod
    def generate_email_html(report: Dict[str, Any]) -> str:
        """Генерирует HTML для email отчёта"""
        period = report['period']
        orders = report['orders']
        prints = report['prints']
        filaments = report['filaments']
        revenue = report['revenue']
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .section h2 {{ color: #2c3e50; margin-top: 0; }}
                .stat {{ display: inline-block; margin: 10px 20px 10px 0; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #3498db; }}
                .stat-label {{ font-size: 12px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f5f5f5; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Ежемесячный отчёт</h1>
                    <p>{period['month_name']} {period['year']}</p>
                    <p style="font-size: 14px;">{period['start_date']} - {period['end_date']}</p>
                </div>
                
                <div class="section">
                    <h2>💰 Выручка</h2>
                    <div class="stat">
                        <div class="stat-value">{revenue['total']:,.2f} ₽</div>
                        <div class="stat-label">Общая выручка</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{revenue['by_type']['repair']:,.2f} ₽</div>
                        <div class="stat-label">Ремонт</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{revenue['by_type']['print']:,.2f} ₽</div>
                        <div class="stat-label">Печать</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📦 Заказы</h2>
                    <div class="stat">
                        <div class="stat-value">{orders['total']}</div>
                        <div class="stat-label">Всего заказов</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{orders['completed']}</div>
                        <div class="stat-label">Завершено</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{orders['avg_check']:,.2f} ₽</div>
                        <div class="stat-label">Средний чек</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{orders['by_type']['repair']}</div>
                        <div class="stat-label">Ремонт</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{orders['by_type']['print']}</div>
                        <div class="stat-label">Печать</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>🖨️ Печать</h2>
                    <div class="stat">
                        <div class="stat-value">{prints['total_jobs']}</div>
                        <div class="stat-label">Всего заданий</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{prints['success_rate']}%</div>
                        <div class="stat-label">Успешных</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{prints['total_grams']:,} г</div>
                        <div class="stat-label">Расход пластика</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{prints['total_hours']} ч</div>
                        <div class="stat-label">Время печати</div>
                    </div>
                    
                    <h3>Расход по типам пластика</h3>
                    <table>
                        <tr><th>Тип</th><th>Расход (г)</th></tr>
                        {''.join([f"<tr><td>{k}</td><td>{v:,} г</td></tr>" for k, v in prints['filament_usage'].items()])}
                    </table>
                </div>
                
                <div class="section">
                    <h2>🧵 Пластик</h2>
                    <div class="stat">
                        <div class="stat-value">{filaments['income']:,} г</div>
                        <div class="stat-label">Приход</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{filaments['expense']:,} г</div>
                        <div class="stat-label">Расход</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{filaments['balance']:,} г</div>
                        <div class="stat-label">Баланс</div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>Отчёт сгенерирован автоматически {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                    <p>CRM Система ремонта 3D принтеров</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

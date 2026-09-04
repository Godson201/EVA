from app.core.config import get_settings
from app.services.job_service import create_celery_app

celery_app = create_celery_app(get_settings())
celery_app.autodiscover_tasks(["app.tasks"])

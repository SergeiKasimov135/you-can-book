"""Ошибки бизнес-логики. В ЛР2 каждая будет преобразована в свой HTTP-код."""


class ServiceError(Exception):
    """Базовая ошибка сервисного слоя."""


class NotFoundError(ServiceError):
    """Объект не найден (HTTP 404)."""


class AlreadyExistsError(ServiceError):
    """Нарушена уникальность: email, название категории (HTTP 409)."""


class BusinessRuleError(ServiceError):
    """Действие запрещено правилами предметной области (HTTP 409/422)."""


class PermissionDeniedError(ServiceError):
    """Недостаточно прав (HTTP 403)."""

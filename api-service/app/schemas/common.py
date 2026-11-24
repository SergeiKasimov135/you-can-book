from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    # from_attributes: схема собирается из атрибутов ORM-объекта (model_validate(obj))
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    detail: str

from app.factory.model_factory import ModelFactory
from app.factory.database_factory import DatabaseFactory

def test_model_factory():
    model = ModelFactory.create_model("gigachat")
    assert model is not None

def test_database_factory():
    db = DatabaseFactory.create_relational_database("postgres")
    assert db is not None

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def _build_url() -> URL | str:
    """Devuelve la URL de conexión a la base pública de la facultad.

    Prioriza ``CHATBOT_PUBLIC_URL``. Si no está definida, la arma a partir de las
    variables ``MARIADB_*`` (host, puerto, usuario, contraseña y base).
    """
    url = os.environ.get("CHATBOT_PUBLIC_URL")
    if url:
        return url

    return URL.create(
        drivername="mysql+pymysql",
        username=os.environ.get("MARIADB_USER", "root"),
        password=os.environ.get("MARIADB_PASSWORD", ""),
        host=os.environ.get("MARIADB_HOST", "localhost"),
        port=int(os.environ.get("MARIADB_PORT", "3306")),
        database=os.environ.get("MARIADB_DB", "chatbot_public"),
        query={"charset": "utf8mb4"},
    )


CHATBOT_PUBLIC_URL = _build_url()

# Motor síncrono: las tools de LangChain se ejecutan en un threadpool dentro del
# agente async, así que no bloquean el event loop. La base es de solo lectura.
engine = create_engine(
    CHATBOT_PUBLIC_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_chatbot_public_session() -> Session:
    """Crea una sesión nueva contra la base pública de la facultad.

    Usarla con un context manager para garantizar el cierre::

        with get_chatbot_public_session() as session:
            ...
    """
    return SessionLocal()

# Make the engine accessible
from sqlalchemy import create_engine
engine = create_engine("sqlite:///data.db") # TODO: an env file containing all paths and tokens etc

from sqlalchemy.orm import Session

# Load calendar models to make them populate Base.metadata
from . import calendar as _

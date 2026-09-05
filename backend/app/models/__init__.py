"""ORM models.

Importing this package registers every mapper, which is what Alembic autogenerate
and ``Base.metadata.create_all`` rely on.
"""

from app.models.activity import Activity, ActivityType
from app.models.category import DEFAULT_CATEGORIES, Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.invite import GroupInvite
from app.models.member import GroupMember, GroupRole
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.user import User

__all__ = [
    "DEFAULT_CATEGORIES",
    "Activity",
    "ActivityType",
    "Category",
    "Expense",
    "ExpenseSplit",
    "Group",
    "GroupInvite",
    "GroupMember",
    "GroupRole",
    "Notification",
    "Payment",
    "SplitMode",
    "User",
]

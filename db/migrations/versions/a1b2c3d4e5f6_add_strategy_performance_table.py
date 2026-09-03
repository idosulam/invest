"""add strategy_performance table

Revision ID: a1b2c3d4e5f6
Revises: 43c3ab91e10f
Create Date: 2026-09-03 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '43c3ab91e10f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'strategy_performance',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('strategy_name', sa.String(100), nullable=False, index=True),
        sa.Column('instrument_id', UUID(as_uuid=True), sa.ForeignKey('instruments.id'), nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('total_return', sa.Numeric(10, 2), nullable=True),
        sa.Column('annualized_return', sa.Numeric(10, 2), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(10, 2), nullable=True),
        sa.Column('sortino_ratio', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_drawdown', sa.Numeric(10, 2), nullable=True),
        sa.Column('win_rate', sa.Numeric(10, 1), nullable=True),
        sa.Column('payoff_ratio', sa.Numeric(10, 2), nullable=True),
        sa.Column('total_trades', sa.Integer, nullable=True),
        sa.Column('total_costs', sa.Numeric(12, 2), nullable=True),
        sa.Column('data_caveat', sa.Text, nullable=True),
        sa.Column('backtest_run_id', UUID(as_uuid=True), sa.ForeignKey('backtest_runs.id'), nullable=True),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('run_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('strategy_name', 'instrument_id', name='uq_strategy_instrument'),
    )


def downgrade() -> None:
    op.drop_table('strategy_performance')

"""Initial schema — all tables + TimescaleDB hypertables

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── articles ──────────────────────────────────────────────────────────
    op.create_table(
        'articles',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source',       sa.String(64),  nullable=False),
        sa.Column('source_tier',  sa.Integer(),   nullable=False, server_default='2'),
        sa.Column('url',          sa.Text(),      nullable=False, unique=True),
        sa.Column('title',        sa.Text(),      nullable=False),
        sa.Column('body',         sa.Text(),      nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fetched_at',   sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('language',     sa.String(8),   nullable=False, server_default='en'),
        sa.Column('is_processed', sa.Boolean(),   nullable=False, server_default='false'),
    )
    op.create_index('ix_articles_published_at', 'articles', ['published_at'])
    op.create_index('ix_articles_source',       'articles', ['source'])
    op.create_index('ix_articles_is_processed', 'articles', ['is_processed'])

    # ── article_analyses ──────────────────────────────────────────────────
    op.create_table(
        'article_analyses',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('article_id',   postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('articles.id'), unique=True, nullable=False),
        sa.Column('analysed_at',  sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        # Event classification
        sa.Column('event_type',        sa.String(64),  nullable=True),
        sa.Column('event_confidence',  sa.Float(),     nullable=True),
        # Sentiment
        sa.Column('sentiment_label',   sa.String(16),  nullable=True),
        sa.Column('sentiment_score',   sa.Float(),     nullable=True),
        sa.Column('geopolitical_stress', sa.Float(),   nullable=True),
        sa.Column('conflict_score',    sa.Float(),     nullable=True),
        # NER
        sa.Column('countries',  postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('actors',     postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('locations',  postgresql.JSONB(),             nullable=True),
        # Clustering
        sa.Column('cluster_id',      sa.Integer(), nullable=True),
        sa.Column('cluster_label',   sa.Text(),    nullable=True),
        sa.Column('embedding_model', sa.String(64), nullable=True),
    )
    op.create_index('ix_article_analyses_event_type',  'article_analyses', ['event_type'])
    op.create_index('ix_article_analyses_cluster_id',  'article_analyses', ['cluster_id'])
    op.create_index('ix_article_analyses_article_id',  'article_analyses', ['article_id'])
    # GIN index for array contains queries (countries filter)
    op.execute(
        "CREATE INDEX ix_article_analyses_countries_gin "
        "ON article_analyses USING GIN (countries)"
    )

    # ── region_signals ────────────────────────────────────────────────────
    op.create_table(
        'region_signals',
        sa.Column('id',           sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('region_code',  sa.String(8),  nullable=False),
        sa.Column('timestamp',    sa.DateTime(timezone=True), nullable=False),
        sa.Column('tension_index',              sa.Float(), nullable=False),
        sa.Column('tension_delta_24h',          sa.Float(), nullable=True),
        sa.Column('conflict_score',             sa.Float(), nullable=True),
        sa.Column('sanctions_score',            sa.Float(), nullable=True),
        sa.Column('political_instability_score', sa.Float(), nullable=True),
        sa.Column('economic_stress_score',      sa.Float(), nullable=True),
        sa.Column('article_count',              sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_unique_constraint(
        'uq_region_signals_region_timestamp',
        'region_signals',
        ['region_code', 'timestamp'],
    )
    op.create_index('ix_region_signals_region_code', 'region_signals', ['region_code'])
    op.create_index('ix_region_signals_timestamp',   'region_signals', ['timestamp'])

    # Convert to TimescaleDB hypertable (partitioned on timestamp)
    # Silently skips if TimescaleDB extension isn't installed (plain Postgres still works)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            ) THEN
                PERFORM create_hypertable(
                    'region_signals', 'timestamp',
                    if_not_exists => TRUE
                );
            END IF;
        END
        $$;
    """)

    # ── market_signals ────────────────────────────────────────────────────
    op.create_table(
        'market_signals',
        sa.Column('id',           sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('timestamp',    sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_hours', sa.Integer(), nullable=False),
        sa.Column('vix_direction',      sa.String(8),  nullable=True),
        sa.Column('vix_confidence',     sa.Float(),    nullable=True),
        sa.Column('gold_bias',          sa.String(8),  nullable=True),
        sa.Column('gold_confidence',    sa.Float(),    nullable=True),
        sa.Column('oil_bias',           sa.String(8),  nullable=True),
        sa.Column('oil_confidence',     sa.Float(),    nullable=True),
        sa.Column('macro_risk_quartile', sa.Integer(), nullable=True),
        sa.Column('feature_snapshot',   postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_market_signals_timestamp',     'market_signals', ['timestamp'])
    op.create_index('ix_market_signals_horizon_hours', 'market_signals', ['horizon_hours'])

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            ) THEN
                PERFORM create_hypertable(
                    'market_signals', 'timestamp',
                    if_not_exists => TRUE
                );
            END IF;
        END
        $$;
    """)

    # ── narrative_clusters ────────────────────────────────────────────────
    op.create_table(
        'narrative_clusters',
        sa.Column('id',           sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cluster_id',   sa.Integer(), nullable=False),   # HDBSCAN id
        sa.Column('detected_at',  sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('label',         sa.Text(),   nullable=False),
        sa.Column('keywords',      postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_stress',    sa.Float(),   nullable=True),
        sa.Column('countries',     postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('stress_7d_ago', sa.Float(),   nullable=True),
        sa.Column('stress_delta_7d', sa.Float(), nullable=True),
        sa.Column('is_emerging',   sa.Boolean(), nullable=False, server_default='false'),
    )
    # UNIQUE on cluster_id — required for the ON CONFLICT upsert in narrative_clusterer.py
    op.create_unique_constraint(
        'uq_narrative_clusters_cluster_id',
        'narrative_clusters',
        ['cluster_id'],
    )

    # ── alerts ────────────────────────────────────────────────────────────
    op.create_table(
        'alerts',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at',   sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('alert_type',   sa.String(32),  nullable=False),
        sa.Column('region_code',  sa.String(8),   nullable=True),
        sa.Column('severity',     sa.String(8),   nullable=False),
        sa.Column('title',        sa.Text(),      nullable=False),
        sa.Column('body',         sa.Text(),      nullable=False),
        sa.Column('is_sent',      sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('metadata',     postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_alerts_created_at',  'alerts', ['created_at'])
    op.create_index('ix_alerts_severity',    'alerts', ['severity'])
    op.create_index('ix_alerts_region_code', 'alerts', ['region_code'])


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('narrative_clusters')
    op.drop_table('market_signals')
    op.drop_table('region_signals')
    op.drop_table('article_analyses')
    op.drop_table('articles')

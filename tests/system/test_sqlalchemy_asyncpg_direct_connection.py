# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# flake8: noqa: ANN001
from datetime import datetime
import os

# [START alloydb_sqlalchemy_asyncpg_connect_iam_authn_direct]
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import event

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request

# [END alloydb_sqlalchemy_asyncpg_connect_iam_authn_direct]


def create_sqlalchemy_engine(
    ip_address: str,
    user: str,
    db_name: str,
) -> sqlalchemy.ext.asyncio.engine.AsyncEngine:
    """Creates a SQLAlchemy connection pool for an AlloyDB instance configured
    using asyncpg.

    Callers are responsible for closing the pool. This implementation uses a
    direct TCP connection with IAM database authentication and not
    the Cloud SQL Python Connector.

    A sample invocation looks like:

        engine = create_sqlalchemy_engine(
                ip_address,
                user,
                db,
        )

        async with engine.connect() as conn:
            result = await conn.execute(sqlalchemy.text("SELECT NOW()"))
            conn.commit()
            time = result.fetchone()

    Args:
        ip_address (str):
            The IP address of an AlloyDB instance, e.g., 10.0.0.1
        user (str):
            The formatted IAM database username.
            e.g., my-email@test.com, service-account@project-id.iam
        db_name (str):
            The name of the database, e.g., mydb
    """
    # [START alloydb_sqlalchemy_asyncpg_connect_iam_authn_direct]
    # initialize Google Auth credentials
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    def get_authentication_token(credentials: Credentials) -> str:
        """Get OAuth2 access token to be used for IAM database authentication"""
        # refresh credentials if expired
        if not credentials.valid:
            request = Request()
            credentials.refresh(request)
        return credentials.token

    engine = create_async_engine(
        # Equivalent URL:
        # postgresql+asyncpg://<user>:empty@<host>:5432/<db_name>
        sqlalchemy.engine.url.URL.create(
            drivername="postgresql+asyncpg",
            username=user,  # your IAM db user, e.g. service-account@project-id.iam
            password="",  # placeholder to be replaced with OAuth2 token
            host=ip_address,  # your AlloyDB instance IP address
            port=5432,
            database=db_name,  # your database name
        ),
        # Because this connection uses an OAuth2 token as a password, you must
        # require SSL, or better, enforce all clients speak SSL on the server
        # side. This ensures the OAuth2 token is not inadvertantly leaked.
        connect_args={"ssl": "require"},
    )

    # set 'do_connect' event listener to replace password with OAuth2 token
    # must use engine.sync_engine as async events are not implemented
    @event.listens_for(engine.sync_engine, "do_connect")
    def auto_iam_authentication(dialect, conn_rec, cargs, cparams) -> None:
        cparams["password"] = get_authentication_token(credentials)

    # [END alloydb_sqlalchemy_asyncpg_connect_iam_authn_direct]
    return engine


async def test_sqlalchemy_asyncpg_time() -> None:
    """Basic test to get time from database using asyncpg with SQLAlchemy."""
    ip_address = os.environ["ALLOYDB_INSTANCE_IP"]  # Private IP for AlloyDB instance
    user = os.environ["ALLOYDB_IAM_USER"]
    db = os.environ["ALLOYDB_DB"]

    engine = create_sqlalchemy_engine(ip_address, user, db)
    # [START alloydb_sqlalchemy_asyncpg_connect_iam_authn_direct]
    # use connection from connection pool to query AlloyDB database
    async with engine.connect() as conn:
        result = await conn.execute(sqlalchemy.text("SELECT NOW()"))
        time = result.fetchone()
        print("Current time is ", time[0])
        # [END alloydb_sqlalchemy_asyncpg_connect_iam_authn_direct]
        curr_time = time[0]
        assert type(curr_time) is datetime
    # cleanup AsyncEngine
    await engine.dispose()

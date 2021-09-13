#!/bin/sh

cd app
SQLALCHEMY_DATABASE_URI=${SQLALCHEMY_DATABASE_URI:-sqlite+aiosqlite:///work.db} ../env/bin/uvicorn main:app

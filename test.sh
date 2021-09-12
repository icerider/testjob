#!/bin/sh

cd app
SQLALCHEMY_DATABASE_URI=sqlite+aiosqlite:///test.db ../env/bin/python -m pytest tests

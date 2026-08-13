from database.database import get_connection, initialize_database


initialize_database()

connection = get_connection()

with connection.cursor() as cursor:
    cursor.execute("SELECT version()")
    result = cursor.fetchone()

print(result["version"])

connection.close()
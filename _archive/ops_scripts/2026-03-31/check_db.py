from core.database import get_db_session, JAVMetadata
import json

session = get_db_session()
row = session.query(JAVMetadata).filter_by(product_code='STAR-471').first()
if row:
    data = {
        "id": row.id,
        "product_code": row.product_code,
        "title": row.title,
        "actors": row.actors,
        "genres": row.genres,
        "cover_url": row.cover_image_url,
        "synopsis": row.synopsis
    }
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print("No data found for STAR-471")
session.close()

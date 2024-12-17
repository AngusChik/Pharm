import csv
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory.settings')
django.setup()

from app.models import Category  # Replace 'app' with your actual app name

def import_categories(file_path):
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            Category.objects.get_or_create(
                name=row['id'],  # Adjust based on your Category model fields
                defaults={
                    'name': row.get('Name', ''),  # Optional fields
                }
            )

if __name__ == '__main__':
    category_csv_file_path = 'Sheet17.csv'
    import_categories(category_csv_file_path)

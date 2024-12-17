import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def generate_price_labels(csv_file, output_pdf):
    c = canvas.Canvas(output_pdf, pagesize=letter)
    width, height = letter
    
    x = 50  # Left margin
    max_width = 275  # Label width for the name
    line_spacing = 18  # Increased spacing between lines in product name
    gap_to_price = 10  # Reduced gap between product name and price
    label_spacing = 90  # Spacing between labels
    y = height - 50

    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "")
            price = row.get("price", "")

            # Draw product name, wrap text to fit max_width
            c.setFont("Helvetica", 16)
            lines = split_text(name, max_width, c)
            for i, line in enumerate(lines):
                c.drawString(x, y - (i * line_spacing), line)

            # Draw price with reduced spacing
            c.setFont("Helvetica-Bold", 22)
            c.drawString(x, y - gap_to_price - (len(lines) * line_spacing), f"Price: ${price}")

            # Add a separator
            c.line(x, y - 20 - gap_to_price - (len(lines) * line_spacing), width - 50, y - 20 - gap_to_price - (len(lines) * line_spacing))

            # Move to the next label position
            y -= label_spacing + (len(lines) * line_spacing)
            if y < 50:  # Start a new page when reaching the bottom
                c.showPage()
                y = height - 50

    c.save()
    print(f"Price labels saved to {output_pdf}")

def split_text(text, max_width, canvas_obj):
    """
    Splits text into multiple lines based on the maximum width.
    """
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        if canvas_obj.stringWidth(test_line) < max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


# Usage
csv_file = "Data.csv"  # Replace with your CSV file
output_pdf = "price.pdf"
generate_price_labels(csv_file, output_pdf)

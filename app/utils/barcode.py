import os
import barcode
from barcode.writer import ImageWriter


def generate_barcode(code, output_folder, barcode_type='code128'):
    """
    Generate a barcode image for the given code

    Args:
        code: The code to encode in the barcode
        output_folder: Folder to save the barcode image
        barcode_type: Type of barcode (default: code128)

    Returns:
        Path to the generated barcode image, or None if failed
    """
    try:
        # Ensure output folder exists
        os.makedirs(output_folder, exist_ok=True)

        # Get barcode class
        barcode_class = barcode.get_barcode_class(barcode_type)

        # Create barcode
        bc = barcode_class(code, writer=ImageWriter())

        # Configure writer options
        options = {
            'module_width': 0.3,
            'module_height': 10,
            'font_size': 10,
            'text_distance': 3,
            'quiet_zone': 5
        }

        # Save barcode
        filename = bc.save(
            os.path.join(output_folder, code),
            options=options
        )

        return filename

    except Exception as e:
        print(f"Error generating barcode for {code}: {e}")
        return None


def generate_barcode_svg(code, barcode_type='code128'):
    """
    Generate a barcode as SVG string

    Args:
        code: The code to encode
        barcode_type: Type of barcode

    Returns:
        SVG string of the barcode
    """
    try:
        from barcode.writer import SVGWriter
        from io import BytesIO

        barcode_class = barcode.get_barcode_class(barcode_type)
        bc = barcode_class(code, writer=SVGWriter())

        buffer = BytesIO()
        bc.write(buffer)
        return buffer.getvalue().decode('utf-8')

    except Exception as e:
        print(f"Error generating SVG barcode for {code}: {e}")
        return None


def get_barcode_data_url(code, barcode_type='code128'):
    """
    Generate a barcode as base64 data URL for embedding in HTML

    Args:
        code: The code to encode
        barcode_type: Type of barcode

    Returns:
        Data URL string
    """
    try:
        from io import BytesIO
        import base64

        barcode_class = barcode.get_barcode_class(barcode_type)
        bc = barcode_class(code, writer=ImageWriter())

        buffer = BytesIO()
        bc.write(buffer, options={
            'module_width': 0.3,
            'module_height': 10,
            'font_size': 10,
            'text_distance': 3,
            'quiet_zone': 5
        })

        buffer.seek(0)
        img_data = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{img_data}"

    except Exception as e:
        print(f"Error generating data URL barcode for {code}: {e}")
        return None

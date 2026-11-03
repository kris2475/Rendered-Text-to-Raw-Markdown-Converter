
import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag


# ============================================================
# RENDERED TEXT TO RAW MARKDOWN CONVERTER
# ============================================================

SUPPORTED_FORMATS = {".html", ".htm", ".xhtml", ".txt"}


def normalise_text(text):
    """Normalise whitespace whilst preserving meaningful content."""

    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    return text


def convert_inline(element):
    """Convert inline HTML elements into Markdown."""

    if isinstance(element, NavigableString):
        return str(element)

    if not isinstance(element, Tag):
        return ""

    tag = element.name.lower()

    content = "".join(convert_inline(child) for child in element.children)

    if tag in ("strong", "b"):
        return f"**{content.strip()}**" if content.strip() else content

    if tag in ("em", "i"):
        return f"*{content.strip()}*" if content.strip() else content

    if tag == "code":
        if element.parent and element.parent.name == "pre":
            return content
        return f"`{content.strip()}`"

    if tag == "a":
        href = element.get("href", "").strip()

        if href:
            return f"[{content.strip()}]({href})"

        return content

    if tag == "br":
        return "\n"

    if tag == "img":
        alt = element.get("alt", "")
        src = element.get("src", "")

        if src:
            return f"![{alt}]({src})"

        return ""

    if tag == "del" or tag == "s" or tag == "strike":
        return f"~~{content.strip()}~~"

    if tag == "sup":
        return f"<sup>{content}</sup>"

    if tag == "sub":
        return f"<sub>{content}</sub>"

    return content


def convert_list(element, level=0):
    """Convert ordered and unordered HTML lists."""

    output = []
    ordered = element.name.lower() == "ol"

    start = int(element.get("start", 1))
    counter = start

    for item in element.find_all("li", recursive=False):

        prefix = "  " * level

        if ordered:
            marker = f"{counter}."
            counter += 1
        else:
            marker = "-"

        item_parts = []

        for child in item.children:

            if isinstance(child, Tag) and child.name.lower() in ("ul", "ol"):
                continue

            if isinstance(child, Tag) and child.name.lower() == "p":
                text = convert_inline(child).strip()
            else:
                text = convert_inline(child).strip()

            if text:
                item_parts.append(text)

        if item_parts:
            output.append(f"{prefix}{marker} {item_parts[0]}")

            for extra in item_parts[1:]:
                output.append(f"{prefix}  {extra}")

        for nested in item.find_all(["ul", "ol"], recursive=False):
            output.extend(convert_list(nested, level + 1))

    return output


def convert_table(element):
    """Convert HTML tables into Markdown tables."""

    rows = []

    for tr in element.find_all("tr"):

        cells = []

        for cell in tr.find_all(["th", "td"], recursive=False):

            value = convert_inline(cell).strip()
            value = re.sub(r"\s+", " ", value)
            value = value.replace("|", r"\|")

            cells.append(value)

        if cells:
            rows.append(cells)

    if not rows:
        return ""

    column_count = max(len(row) for row in rows)

    for row in rows:
        row.extend([""] * (column_count - len(row)))

    output = []

    header = rows[0]

    output.append("| " + " | ".join(header) + " |")
    output.append("| " + " | ".join(["---"] * column_count) + " |")

    for row in rows[1:]:
        output.append("| " + " | ".join(row) + " |")

    return "\n".join(output)


def convert_block(element):
    """Convert HTML block elements into Markdown."""

    if isinstance(element, NavigableString):
        text = str(element).strip()
        return text if text else ""

    if not isinstance(element, Tag):
        return ""

    tag = element.name.lower()

    if tag in ("script", "style", "noscript", "svg"):
        return ""

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):

        level = int(tag[1])
        content = convert_inline(element).strip()

        return f"{'#' * level} {content}"

    if tag in ("ul", "ol"):
        return "\n".join(convert_list(element))

    if tag == "table":
        return convert_table(element)

    if tag == "pre":

        code = element.get_text()
        code = code.strip("\n")

        code_element = element.find("code")

        language = ""

        if code_element:
            classes = code_element.get("class", [])

            for class_name in classes:
                if class_name.startswith("language-"):
                    language = class_name.replace("language-", "")
                    break

        return f"```{language}\n{code}\n```"

    if tag == "blockquote":

        content = convert_children(element)

        quoted_lines = []

        for line in content.splitlines():
            quoted_lines.append("> " + line if line else ">")

        return "\n".join(quoted_lines)

    if tag == "hr":
        return "---"

    if tag == "p":

        content = convert_inline(element).strip()

        return content

    if tag == "div":

        content = convert_children(element)

        return content

    if tag in ("article", "section", "main", "body"):

        return convert_children(element)

    if tag in ("header", "footer", "nav"):
        return ""

    if tag == "figure":
        return convert_children(element)

    if tag == "figcaption":
        return f"*{convert_inline(element).strip()}*"

    if tag == "details":
        return convert_children(element)

    if tag == "summary":
        return f"**{convert_inline(element).strip()}**"

    return convert_children(element)


def convert_children(element):
    """Convert all child elements."""

    output = []

    for child in element.children:

        converted = convert_block(child)

        if converted:
            output.append(converted)

    return "\n\n".join(output)


def clean_markdown(markdown):
    """Clean excessive blank lines and whitespace."""

    markdown = normalise_text(markdown)

    # Remove trailing whitespace
    markdown = "\n".join(
        line.rstrip() for line in markdown.splitlines()
    )

    # Limit excessive blank lines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)

    # Remove spaces around blank lines
    markdown = re.sub(r"\n[ \t]+\n", "\n\n", markdown)

    return markdown.strip() + "\n"


def convert_html_to_markdown(html):
    """Convert complete HTML document into Markdown."""

    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted HTML elements
    for element in soup.find_all(
        ["script", "style", "noscript", "svg",
         "iframe", "nav", "footer"]
    ):
        element.decompose()

    # Prefer the document body
    body = soup.body if soup.body else soup

    markdown = convert_children(body)

    return clean_markdown(markdown)


def convert_text_file(text):
    """Handle plain text input."""

    text = normalise_text(text)

    return clean_markdown(text)


def convert_file(input_filename):
    """Read input file and generate raw Markdown output."""

    source = Path(input_filename).expanduser()

    if not source.exists():
        print(f"\nERROR: Input file not found:\n{source}")
        return

    if not source.is_file():
        print("\nERROR: The selected path is not a file.")
        return

    extension = source.suffix.lower()

    if extension not in SUPPORTED_FORMATS:
        print("\nERROR: Unsupported file format.")
        print("Supported formats: HTML, HTM, XHTML, TXT")
        return

    output_file = source.with_suffix(".md")

    if output_file.resolve() == source.resolve():
        print("\nERROR: Input and output files cannot be the same.")
        return

    try:

        print("\nReading input file...")

        content = source.read_text(
            encoding="utf-8",
            errors="replace"
        )

        print("Converting content...")

        if extension in (".html", ".htm", ".xhtml"):

            markdown = convert_html_to_markdown(content)

        elif extension == ".txt":

            markdown = convert_text_file(content)

        else:
            return

        print("Writing raw Markdown...")

        output_file.write_text(
            markdown,
            encoding="utf-8",
            newline="\n"
        )

        print("\n" + "=" * 55)
        print("CONVERSION COMPLETE")
        print("=" * 55)

        print(f"\nInput file:  {source}")
        print(f"Output file: {output_file}")
        print(f"Characters:  {len(markdown):,}")
        print(f"File size:   {output_file.stat().st_size:,} bytes")

        print("\nOutput contains raw Markdown source.")
        print("It is ready to open and edit as a README.md file.")

        print("=" * 55)

    except PermissionError:
        print("\nERROR: Permission denied when reading or writing file.")

    except Exception as error:
        print(f"\nERROR: Conversion failed: {error}")


def main():

    print("=" * 55)
    print("       RENDERED TEXT TO RAW MARKDOWN CONVERTER")
    print("=" * 55)

    if len(sys.argv) > 1:

        input_filename = " ".join(sys.argv[1:])

    else:

        input_filename = input(
            "\nEnter the full path of the input file:\n> "
        ).strip().strip('"')

    if not input_filename:
        print("\nNo input file specified.")
        return

    convert_file(input_filename)

    input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()

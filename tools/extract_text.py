#!/usr/bin/env python3
"""Extract the Red Book PDF's text with page markers, for redbook_to_gedcom.py.

Usage: python3 tools/extract_text.py red_book.pdf book.txt   (needs: pip install pypdf)
"""
import sys
from pypdf import PdfReader

reader = PdfReader(sys.argv[1])
with open(sys.argv[2], "w", encoding="utf-8") as out:
    for i, page in enumerate(reader.pages):
        out.write(f"\n=====PAGE {i + 1}=====\n" + (page.extract_text() or ""))

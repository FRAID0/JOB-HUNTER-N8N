"""
Document Hub (Intelligent Document Registry)
Scans the candidate's document directory, indexes all PDFs,
categorizes their semantic purpose, and intelligently resolves what file
to upload based on the web page's request (e.g. CV vs Zeugnisse vs Immatrikulation).
Prevents ever uploading a CV into a Zeugnisse slot or vice-versa!
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional


class DocumentCategory:
    CV = "cv"
    ANSCHREIBEN = "anschreiben"
    ZEUGNISSE = "zeugnisse"
    IMMATRIKULATION = "immatrikulation"
    ARBEITSZEUGNIS = "arbeitszeugnis"
    SONSTIGE = "sonstige"


class DocumentHub:
    def __init__(self, docs_dir: str = "d:/N8N/documents"):
        self.docs_dir = Path(docs_dir)
        self.inventory: Dict[str, List[Path]] = {
            DocumentCategory.CV: [],
            DocumentCategory.ANSCHREIBEN: [],
            DocumentCategory.ZEUGNISSE: [],
            DocumentCategory.IMMATRIKULATION: [],
            DocumentCategory.ARBEITSZEUGNIS: [],
            DocumentCategory.SONSTIGE: [],
        }
        self.scan_documents()

    def scan_documents(self) -> None:
        """Scans the documents directory and categorizes each file."""
        if not self.docs_dir.exists():
            return

        for p in self.docs_dir.glob("*.pdf"):
            fname = p.name.lower()
            
            # 1. CV / Lebenslauf
            if any(w in fname for w in ["cv", "lebenslauf", "resume"]):
                self.inventory[DocumentCategory.CV].append(p)

            # 2. Anschreiben / Motivationsschreiben
            elif any(w in fname for w in ["anschreiben", "cover", "motivation"]):
                self.inventory[DocumentCategory.ANSCHREIBEN].append(p)

            # 3. Immatrikulationsbescheinigung / Studienbescheinigung
            elif any(w in fname for w in ["studienbescheinigung", "immatrikulation", "student"]):
                self.inventory[DocumentCategory.IMMATRIKULATION].append(p)
                # An enrollment certificate also counts as qualification/zeugnis
                self.inventory[DocumentCategory.ZEUGNISSE].append(p)

            # 4. Notenspiegel / Studiengang / Transcript / Zeugnisse
            elif any(w in fname for w in ["notenspiegel", "studiengang", "zeugnis", "transcript", "diplom"]):
                self.inventory[DocumentCategory.ZEUGNISSE].append(p)

            # 5. Arbeitszeugnis / Praktikum
            elif any(w in fname for w in ["praktikum", "arbeitszeugnis", "zeugnis", "fraid"]):
                self.inventory[DocumentCategory.ARBEITSZEUGNIS].append(p)
                self.inventory[DocumentCategory.ZEUGNISSE].append(p)

            else:
                self.inventory[DocumentCategory.SONSTIGE].append(p)

    def resolve_document(self, context_text: str) -> Optional[Path]:
        """
        Determines the best matching document file based on the dropzone's label/context text.
        Guarantees that a Zeugnisse request will NEVER return a CV!
        """
        txt = (context_text or "").lower()

        # Priority 1: Zeugnisse / Notenspiegel / Qualifikationen
        if any(w in txt for w in ["zeugnis", "notenspiegel", "qualifikation", "zertifikat", "diplom", "transcript", "beleg"]):
            candidates = self.inventory.get(DocumentCategory.ZEUGNISSE, [])
            # Prioritize transcripts and grades first
            for cand in candidates:
                if any(w in cand.name.lower() for w in ["notenspiegel", "studiengang", "transcript"]):
                    return cand
            # Next prioritize certificates/diplomas
            for cand in candidates:
                if any(w in cand.name.lower() for w in ["zeugnis", "zertifikat", "diplom"]):
                    return cand
            if candidates:
                return candidates[0]

        # Priority 2: Immatrikulationsbescheinigung
        if any(w in txt for w in ["immatrikulation", "studienbescheinigung", "studiennachweis"]):
            candidates = self.inventory.get(DocumentCategory.IMMATRIKULATION, [])
            if candidates:
                return candidates[0]

        # Priority 3: Arbeitszeugnis / Praktikumszeugnis
        if any(w in txt for w in ["arbeitszeugnis", "praktikum", "referenz"]):
            candidates = self.inventory.get(DocumentCategory.ARBEITSZEUGNIS, [])
            if candidates:
                return candidates[0]

        # Priority 4: Anschreiben
        if any(w in txt for w in ["anschreiben", "motivationsschreiben", "cover"]):
            candidates = self.inventory.get(DocumentCategory.ANSCHREIBEN, [])
            if candidates:
                return candidates[0]

        # Priority 5: Lebenslauf / CV
        if any(w in txt for w in ["lebenslauf", "cv", "resume", "curriculum", "werdegang", "profil"]):
            candidates = self.inventory.get(DocumentCategory.CV, [])
            if candidates:
                return candidates[0]

        # Explicit check for "Andere" / "Sonstige" / "Optional"
        if any(w in txt for w in ["andere", "sonstige", "optional", "weitere", "zusatz"]):
            # Do NOT return CV. If an Arbeitszeugnis or Zeugnis exists, can offer it, otherwise None.
            az = self.inventory.get(DocumentCategory.ARBEITSZEUGNIS, [])
            if az:
                return az[0]
            z = self.inventory.get(DocumentCategory.ZEUGNISSE, [])
            if z:
                return z[0]
            return None

        # No blind fallback to CV: only return CV if explicitly asked
        return None

    def summary(self) -> str:
        lines = ["Document Inventory:"]
        for cat, files in self.inventory.items():
            if files:
                lines.append(f"  [{cat}]: {[f.name for f in files]}")
        return "\n".join(lines)

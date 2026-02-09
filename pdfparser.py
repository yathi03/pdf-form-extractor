import json
from typing import Dict, List

FIELD_MAP = {

    "policy_number": ["Text7"],
    "policyholder_name": ["NAME OF INSURED First Middle Last"],

  
    "incident_date": ["DATE OF LOSS", "TEXT3"],
    "incident_time": ["TEXT4"],
    "incident_location_detail": ["STREET LOCATION OF LOSS"],
    "incident_description": ["DESCRIPTION OF ACCIDENT ACORD 101 Additional Remarks Schedule may be attached if more space is required"],

  
    "claimant": ["NAME OF INSURED First Middle Last"],
    "third_partie": ["TEXT48"],
    "third_partie_contact": ["CELL HOME BUS PRIMARY_6"],
    "third_partie_email":["PRIMARY EMAIL ADDRESS_6"],


    "Asset Type":["NON  VEHICLE"],
    "Asset ID":["VIN"],
    "estimated_damage":["ESTIMATE AMOUNT_2"],

}




MANDATORY_FIELDS = [
    "policy_number",
    "policyholder_name",
    "incident_date",
    "incident_description",
    "estimated_damage"
]



class PDFFormExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract(self) -> Dict[str, str]:
        data = self._extract_form_fields()
        if data:
            return data

        data = self._extract_with_pdfplumber()
        if data:
            return data

        return self._extract_with_ocr()

    def _extract_form_fields(self) -> Dict[str, str]:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(self.pdf_path)
            fields = reader.get_fields()
            if not fields:
                return {}

            extracted = {}
            for key, field in fields.items():
                value = field.get("/V", "")
                extracted[str(key).strip()] = str(value).strip()
            return extracted
        except Exception:
            return {}

    def _extract_with_pdfplumber(self) -> Dict[str, str]:
        try:
            import pdfplumber
            extracted = {}
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    for line in text.splitlines():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            extracted[key.strip()] = value.strip()
            return extracted
        except Exception:
            return {}

    def _extract_with_ocr(self) -> Dict[str, str]:
        try:
            import pytesseract
            from pdf2image import convert_from_path
            extracted = {}
            images = convert_from_path(self.pdf_path, dpi=300)
            for img in images:
                text = pytesseract.image_to_string(img)
                for line in text.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        extracted[key.strip()] = value.strip()
            return extracted
        except Exception:
            return {}


def extract_mapped_fields_as_json(pdf_path: str) -> Dict[str, str]:
    extractor = PDFFormExtractor(pdf_path)
    raw_data = extractor.extract()
    final_data = {}

    for output_key, source_keys in FIELD_MAP.items():
        for source_key in source_keys:
            for raw_key, raw_value in raw_data.items():
                if source_key.lower() == raw_key.lower():
                    final_data[output_key] = raw_value
                    break

    time_value = final_data.get("incident_time", "").strip()

    def is_checked(val):
        return str(val).strip().lower() in ["/yes", "yes", "on", "true"]

    am_checked = is_checked(raw_data.get("Check Box5"))
    pm_checked = is_checked(raw_data.get("Check Box6"))

    if time_value:
        if am_checked:
            final_data["incident_time"] = f"{time_value} AM"
        elif pm_checked:
            final_data["incident_time"] = f"{time_value} PM"
        else:
            final_data["incident_time"] = time_value

 

    if not final_data.get("incident_description") and final_data.get("damage_description"):
        final_data["incident_description"] = final_data["damage_description"]

    return final_data




def find_missing_fields(extracted: Dict[str, str]) -> List[str]:
    return [
        field for field in MANDATORY_FIELDS
        if not extracted.get(field)
    ]

def parse_estimated_damage(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def determine_routing(extracted: Dict[str, str], missing_fields: List[str]):
    description = extracted.get("incident_description", "").lower()
    estimated_damage = parse_estimated_damage(extracted.get("estimated_damage"))

    # Rule 1: Missing mandatory fields
    if missing_fields:
        return (
            "Manual review",
            f"Mandatory fields missing: {', '.join(missing_fields)}"
        )

    # Rule 2: Fraud indicators
    if any(word in description for word in ["fraud", "inconsistent", "staged"]):
        return (
            "Investigation Flag",
            "Incident description contains potential fraud indicators"
        )

    # Rule 3: Fast-track
    if estimated_damage < 25000:
        return (
            "Fast-track",
            "Estimated damage below 25,000"
        )

    return (
        "Standard Processing",
        "Estimated damage exceeds fast-track threshold"
    )


def process_fnol(pdf_path: str) -> Dict:
    extracted_fields = extract_mapped_fields_as_json(pdf_path)
    missing_fields = find_missing_fields(extracted_fields)
    route, reasoning = determine_routing(extracted_fields, missing_fields)

    return {
        "extractedFields": extracted_fields,
        "missingFields": missing_fields,
        "recommendedRoute": route,
        "reasoning": reasoning
    }


if __name__ == "__main__":
    result = process_fnol("form.pdf")
    print(json.dumps(result, indent=2))



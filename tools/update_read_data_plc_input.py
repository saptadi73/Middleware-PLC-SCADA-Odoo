import csv
import json
from pathlib import Path

MAPPING_PATH = Path("app/reference/READ_DATA_PLC_GENERATED.json")
OUTPUT_PATH = Path("app/reference/read_data_plc_input.csv")


def format_value(data_type: str, sample, scale):
    data_type = (data_type or "").upper()
    if data_type == "ASCII":
        return str(sample) if sample is not None else ""
    if data_type == "BOOLEAN":
        return "1"
    if data_type == "REAL":
        if sample in (None, ""):
            return ""
        scale_value = float(scale) if scale not in (None, "") else 1.0
        value = float(sample) / scale_value
        if scale_value == 1.0:
            return str(int(value)) if value.is_integer() else str(value)
        return f"{value:.2f}"
    return str(sample) if sample is not None else ""


def format_length(data_type: str, length):
    data_type = (data_type or "").upper()
    if data_type == "ASCII":
        return str(length or "")
    if data_type == "BOOLEAN":
        return "1"
    if data_type == "REAL":
        return "5"
    return str(length or "")


def main():
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    rows = []
    for item in mapping.get("raw_list", []):
        data_type = item.get("Data Type")
        sample = item.get("Sample")
        scale = item.get("scale", "")
        rows.append({
            "No": item.get("No", ""),
            "Informasi": item.get("Informasi", ""),
            "Data Type": data_type,
            "length": format_length(data_type, item.get("length")),
            "Sample": sample if sample is not None else "",
            "scale": scale if scale is not None else "",
            "DM - Memory": item.get("DM - Memory", ""),
            "Value": format_value(data_type, sample, scale),
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "No",
                "Informasi",
                "Data Type",
                "length",
                "Sample",
                "scale",
                "DM - Memory",
                "Value",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

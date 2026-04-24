import csv
import io
import json

def json_to_csv(params: dict) -> dict:
    data = params.get("data", [])
    if not data or not isinstance(data, list) or not isinstance(data[0], dict):
        return {"error": "Expected 'data' to be a list of dictionaries"}
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    return {"csv": output.getvalue()}

def validate_email_list(params: dict) -> dict:
    emails = params.get("emails", [])
    if not isinstance(emails, list):
        return {"error": "Expected 'emails' to be a list of strings"}
        
    import re
    email_regex = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
    
    valid = []
    invalid = []
    
    for email in emails:
        if email_regex.match(str(email)):
            valid.append(email)
        else:
            invalid.append(email)
            
    return {
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "valid_emails": valid,
        "invalid_emails": invalid
    }

def deduplicate_records(params: dict) -> dict:
    records = params.get("records", [])
    key = params.get("key", None)
    
    if not isinstance(records, list):
        return {"error": "Expected 'records' to be a list"}
        
    seen = set()
    deduped = []
    
    for item in records:
        if key and isinstance(item, dict):
            val = str(item.get(key))
            if val not in seen:
                seen.add(val)
                deduped.append(item)
        else:
            # Simple dedup for lists of strings/numbers
            val = str(item)
            if val not in seen:
                seen.add(val)
                deduped.append(item)
                
    return {
        "original_count": len(records),
        "deduplicated_count": len(deduped),
        "duplicates_removed": len(records) - len(deduped),
        "records": deduped
    }

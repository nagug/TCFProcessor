# IAB TCF String Processor

## Overview

This Python script provides a class, `TCFProcessor`, designed to parse IAB Transparency and Consent Framework (TCF) v1.1 and v2 consent strings. It integrates data from the official IAB Global Vendor List (GVL) and CMP List JSON files to offer convenient methods for querying various aspects of the user's consent choices and related metadata.

The core TCF string decoding relies on the `iab-tcf` library. This class builds upon that by adding GVL/CMP list integration and higher-level query functions.

## Features

* Decodes IAB TCF v1.1 and v2 consent strings.
* Loads and utilizes data from IAB Global Vendor List (`vendor-list.json`) and CMP List (`cmp-list.json`).
* Extracts key TCF metadata (version, timestamps, CMP ID, vendor list version, etc.).
* Retrieves lists of vendors for whom explicit consent has been granted (either IDs only or with full details derived from GVL).
* Retrieves details for the Consent Management Platform (CMP) specified in the string (using CMP list data).
* Identifies vendors for whom the user has established a Legitimate Interest basis.
* Filters consented vendors based on the purposes, special purposes, features, special features, and flexible purposes they declare in the GVL.
* Retrieves vendor-specific URLs (Privacy Policy, Device Storage Disclosure) from the GVL.
* Filters consented vendors based on their declared cookie usage (`usesCookies`) and non-cookie access (`usesNonCookieAccess`) flags in the GVL.
* Includes basic error handling for file loading and TCF string decoding errors.

## Prerequisites

* **Python:** Version 3.x recommended.
* **Required Libraries:** `iab-tcf` (see Installation).
* **Data Files:** You need the official IAB TCF data files (see Setup).

## Installation

The script relies on the `iab-tcf` library for the core TCF string decoding. Install it using pip:

```bash
pip install iab-tcf
```

## Setup

Before running the script or using the `TCFProcessor` class, you need to obtain the necessary data files:

1.  **Global Vendor List (GVL):**
    * Download the latest TCF v2 GVL file. This is usually available from the [IAB Tech Lab Europe website](https://iabeurope.eu/vendor-list-tcf-v2-0/) or their tools repository. Look for a file typically named `vendor-list.json`.
    * Save this file as `vendor-list.json` in the same directory as your Python script, or provide the correct file path when creating a `TCFProcessor` instance.

2.  **CMP List:**
    * Download the latest CMP list file. This is also typically available from IAB Tech Lab resources. Look for a file named `cmp-list.json`.
    * Save this file as `cmp-list.json` in the same directory as your Python script, or provide the correct file path during instantiation.

**Note:** Ensure you are using GVL and CMP list versions that correspond to the TCF strings you are processing for accurate results.

## Usage

### 1. Import and Instantiate

First, save the Python code containing the `TCFProcessor` class into a file (e.g., `tcf_processor.py`). Then, import and create an instance of the class, providing the TCF consent string and optionally the paths to your data files.

```python
# Import the class (assuming it's saved in tcf_processor.py)
from tcf_processor import TCFProcessor
import json # For pretty printing output

# --- Configuration ---
# Replace with the actual TCF string you want to process
consent_string = "CP5QSAAP5QSAAAxAENAAAAPOAAAAAAAAAAA.YAAAAAAAAAAA"
gvl_file = "vendor-list.json"
cmp_list_file = "cmp-list.json"
# --- End Configuration ---

# Create an instance
# This automatically loads files and decodes the string
print("Initializing TCFProcessor...")
processor = TCFProcessor(
    consent_string=consent_string,
    gvl_filepath=gvl_file,
    cmp_list_filepath=cmp_list_file
)

# Check for critical initialization errors (e.g., failed TCF decoding)
if processor.error_state:
    print(f"\nCRITICAL ERROR during initialization: {processor.error_state}")
    print("Script may exit or results may be incomplete.")
    # Handle error appropriately, e.g., exit()
    # exit(1)
else:
    print("\nInitialization successful (or only non-critical warnings occurred).")

# Now you can call the various methods on the 'processor' object.
```

### 2. Get TCF Metadata

Retrieve general information embedded within the TCF string.

```python
if not processor.error_state: # Only proceed if decoding likely succeeded
    print("\n--- TCF Metadata ---")
    metadata = processor.get_metadata()
    try:
        # Use default=str as a fallback for any unexpected non-serializable types
        print(json.dumps(metadata, indent=2, default=str))
    except Exception as e:
        print(f"Error displaying metadata: {e}\nRaw: {metadata}")
```

* **Output:** A dictionary containing fields like `tcf_version`, `created`, `last_updated`, `cmp_id`, `cmp_version`, `vendor_list_version`, `consent_language`, etc. Includes `initialization_error` key if applicable.

### 3. Get Consented Vendors

Retrieve vendors for whom explicit consent is granted in the string.

```python
if not processor.error_state:
    # --- Get List of IDs Only ---
    print("\n--- Consented Vendor IDs ---")
    consented_ids = processor.get_consented_vendors(include_details=False)
    print(f"Found {len(consented_ids)} consented IDs.")
    print("Sample IDs:", consented_ids[:10], "..." if len(consented_ids) > 10 else "")

    # --- Get List with Full Details ---
    print("\n--- Consented Vendor Details (Sample) ---")
    consented_details = processor.get_consented_vendors(include_details=True)
    if consented_details:
        print(f"Showing details for first {min(2, len(consented_details))} vendors:")
        try:
            print(json.dumps(consented_details[:2], indent=2, default=str))
        except Exception as e:
            print(f"Error displaying vendor details: {e}\nRaw: {consented_details[:2]}")
    else:
        print("No consented vendors found.")
```

* **Output (`include_details=False`):** A list of integers representing the consented vendor IDs.
* **Output (`include_details=True`):** A list of dictionaries, where each dictionary contains detailed information about a consented vendor, pulled from the GVL.

### 4. Get CMP Details

Retrieve details about the Consent Management Platform (CMP) listed in the TCF string, using the `cmp-list.json` file.

```python
if not processor.error_state:
    print("\n--- CMP Details ---")
    cmp_details = processor.get_cmp_details()
    try:
        print(json.dumps(cmp_details, indent=2, default=str))
    except Exception as e:
        print(f"Error displaying CMP details: {e}\nRaw: {cmp_details}")
```

* **Output:** A dictionary containing the details for the specified CMP as found in `cmp-list.json`. If the CMP ID is not found, not set, or the file wasn't loaded, it returns a dictionary indicating this, potentially with an 'error' key.

### 5. Get Vendors Using Legitimate Interest

Identify vendors for whom the user has established a Legitimate Interest (LI) basis via the TCF string. Also shows the LI purposes declared by those vendors in the GVL.

```python
if not processor.error_state:
    print("\n--- Vendors with Legitimate Interest Established ---")
    li_vendors = processor.get_vendors_using_legitimate_interest()
    print(f"Found {len(li_vendors)} vendors with LI established.")
    if li_vendors:
        # Print details for a sample
        li_sample = {k: li_vendors[k] for k in list(li_vendors)[:2]}
        try:
            print(json.dumps(li_sample, indent=2, default=str))
            if len(li_vendors) > 2: print("...")
        except Exception as e:
            print(f"Error displaying LI vendors: {e}\nRaw: {li_sample}")
```

* **Output:** A dictionary mapping vendor IDs (int) to `{'name': str, 'declared_li_purposes': list[int]}`.

### 6. Get Vendors by Purpose/Feature Consent

Filter vendors who have user consent *and* declare specific purposes or features in their GVL entry.

```python
if not processor.error_state:
    # --- Example 1: Vendors consented for Purpose 1 ---
    print("\n--- Consented Vendors for Purpose 1 ---")
    p1_vendors = processor.get_consented_vendors_for_purposes([1])
    print(f"Found {len(p1_vendors)} vendors.")
    # (Add print sample if desired)

    # --- Example 2: Vendors consented for BOTH Purpose 3 AND Purpose 4 ---
    print("\n--- Consented Vendors for Purposes 3 AND 4 ---")
    p3_and_p4_vendors = processor.get_consented_vendors_for_purposes([3, 4], require_all=True)
    print(f"Found {len(p3_and_p4_vendors)} vendors.")
    # (Add print sample if desired)

    # --- Example 3: Vendors consented for Special Feature 1 ---
    print("\n--- Consented Vendors for Special Feature 1 ---")
    sf1_vendors = processor.get_consented_vendors_for_special_features([1])
    print(f"Found {len(sf1_vendors)} vendors.")
    # (Add print sample if desired)
```

* **Output:** A dictionary mapping matching vendor IDs (int) to `{'name': str, 'matched_ids': list[int]}`, where `matched_ids` are the specific required IDs found in the vendor's GVL declaration.
* Use similar method calls for:
    * `get_consented_vendors_for_special_purposes([...])`
    * `get_consented_vendors_for_features([...])`
    * `get_consented_vendors_for_flexible_purposes([...])`
* The `require_all` parameter (default `False`) controls whether vendors must declare ALL specified IDs (`True`) or AT LEAST ONE (`False`).

### 7. Get Vendor URLs

Retrieve specific URLs for a given vendor ID from the GVL.

```python
if not processor.error_state:
    vendor_id_to_lookup = 755 # Example: Google
    print(f"\n--- URLs for Vendor {vendor_id_to_lookup} ---")
    urls = processor.get_vendor_urls(vendor_id_to_lookup)
    try:
        print(json.dumps(urls, indent=2, default=str))
    except Exception as e:
        print(f"Error displaying URLs: {e}\nRaw: {urls}")

    # Example for a non-existent vendor
    urls_nf = processor.get_vendor_urls(99999)
    print("\n--- URLs for Vendor 99999 (Not Found) ---")
    print(json.dumps(urls_nf, indent=2, default=str))
```

* **Output:** A dictionary containing `'policyUrl'` and `'deviceStorageDisclosureUrl'`. Includes an `'error'` key if the vendor ID was not found in the loaded GVL or if the GVL itself wasn't loaded.

### 8. Get Vendors by Cookie/Non-Cookie Usage

Filter consented vendors based on their declaration of using cookies or non-cookie access methods in the GVL.

```python
if not processor.error_state:
    # --- Vendors Using Cookies ---
    print("\n--- Consented Vendors Using Cookies ---")
    cookie_vendors = processor.get_consented_vendors_using_cookies()
    print(f"Found {len(cookie_vendors)} vendors.")
    if cookie_vendors:
        # Print sample
        cookie_sample = {k: cookie_vendors[k] for k in list(cookie_vendors)[:5]}
        print(json.dumps(cookie_sample, indent=2, default=str))
        if len(cookie_vendors) > 5: print("...")

    # --- Vendors Using Non-Cookie Access ---
    print("\n--- Consented Vendors Using Non-Cookie Access ---")
    non_cookie_vendors = processor.get_consented_vendors_using_non_cookie_access()
    print(f"Found {len(non_cookie_vendors)} vendors.")
    if non_cookie_vendors:
         # Print sample
        non_cookie_sample = {k: non_cookie_vendors[k] for k in list(non_cookie_vendors)[:5]}
        print(json.dumps(non_cookie_sample, indent=2, default=str))
        if len(non_cookie_vendors) > 5: print("...")
```

* **Output:** A dictionary mapping matching vendor IDs (int) to their names (str).

## Error Handling

* **File Loading:** If `vendor-list.json` or `cmp-list.json` cannot be found or parsed, warnings are printed during initialization (`TCFProcessor(...)`). Methods relying on that data will return empty results or results indicating that the data is missing/incomplete (e.g., vendor names showing as 'unknown').
* **TCF Decoding:** If the provided `consent_string` is empty or invalid, `iab_tcf.decode` will likely raise an exception. This is caught during initialization, a critical error message is stored in `processor.error_state`, and `processor.consent_object` will be `None`. Most methods check for `processor.consent_object` or `processor.error_state` and will return empty results (e.g., `[]` or `{}`) or include an error indicator if decoding failed. You should check `processor.error_state` after creating the instance.
* **JSON Serialization:** The example usage includes `default=str` in `json.dumps` calls as a fallback to prevent TypeErrors if any unexpected non-serializable data types (beyond standard types, handled `datetime`, and handled `bytes`) remain in the results.

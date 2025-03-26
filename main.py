import json
from datetime import datetime, timezone
# Attempt to import decode from iab_tcf. If the library is not installed,
# the script will fail here, which is expected.
try:
    from iab_tcf import decode
except ImportError:
    print("ERROR: The 'iab-tcf' library is not installed.")
    print("Please install it using: pip install iab-tcf")
    exit(1)

class TCFProcessor:
    """
    Processes an IAB TCF consent string using associated Global Vendor List (GVL)
    and CMP List data to provide easy access to consent information and metadata.

    Handles loading data files, decoding the TCF string, and provides methods
    for querying various aspects like consented vendors, metadata, CMP details,
    legitimate interest vendors, and vendors based on purpose or cookie usage.

    Attributes:
        consent_string (str): The TCF consent string being processed.
        gvl_filepath (str): Path to the GVL JSON file.
        cmp_list_filepath (str): Path to the CMP List JSON file.
        gvl_data (dict | None): Raw data loaded from the GVL file.
        gvl_vendors_dict (dict): Vendors from GVL, keyed by string vendor ID.
        cmp_list_data (dict | None): Raw data loaded from the CMP list file.
        cmp_list_dict (dict): CMPs from the CMP list, keyed by string CMP ID.
        consent_object (ConsentV1 | ConsentV2 | None): The decoded object from iab_tcf.decode.
        error_state (str | None): Stores critical error messages from initialization (e.g., decode failure).
    """

    def __init__(self,
                 consent_string: str,
                 gvl_filepath: str = 'vendor-list.json',
                 cmp_list_filepath: str = 'cmp-list.json'):
        """
        Initializes the TCFProcessor instance, loads data files, and decodes the string.

        Args:
            consent_string (str): The TCF consent string to process. Can be None or empty.
            gvl_filepath (str): The path to the GVL JSON file (vendors).
                                Defaults to 'vendor-list.json'.
            cmp_list_filepath (str): The path to the CMP List JSON file.
                                     Defaults to 'cmp-list.json'.
        """
        if not isinstance(consent_string, str):
             # Handle cases where None or non-string might be passed
             consent_string = ""
             print("Warning: Consent string was not a string, treating as empty.")

        self.consent_string = consent_string
        self.gvl_filepath = gvl_filepath
        self.cmp_list_filepath = cmp_list_filepath

        # Initialize attributes
        self.gvl_data = None
        self.gvl_vendors_dict = {}
        self.cmp_list_data = None
        self.cmp_list_dict = {}
        self.consent_object = None
        self.error_state = None # Stores critical init errors

        # Perform loading and decoding
        self._load_gvl()
        self._load_cmp_list()
        self._decode_tcf() # Sets self.consent_object and potentially self.error_state

    def _load_gvl(self):
        """
        Internal method to load the GVL data (vendors) from the specified file path.
        Handles file not found and JSON decoding errors, storing results in instance attributes.
        Prints warnings on failure but doesn't set the main error_state.
        """
        print(f"Attempting to load GVL data from '{self.gvl_filepath}'...")
        try:
            with open(self.gvl_filepath, 'r', encoding='utf-8') as f:
                self.gvl_data = json.load(f)
            # Assumes GVL structure has a top-level 'vendors' key mapped to a dict
            self.gvl_vendors_dict = self.gvl_data.get('vendors', {})
            # Ensure vendor keys are strings
            self.gvl_vendors_dict = {str(k): v for k, v in self.gvl_vendors_dict.items()}
            print(f"Successfully loaded GVL data. Found {len(self.gvl_vendors_dict)} vendors.")
        except FileNotFoundError:
            print(f"WARNING: GVL file '{self.gvl_filepath}' not found. Vendor details lookup will be limited.")
            self.gvl_vendors_dict = {} # Ensure it's empty
        except json.JSONDecodeError:
            print(f"WARNING: Could not decode JSON from GVL file '{self.gvl_filepath}'. Check format. Vendor details lookup limited.")
            self.gvl_vendors_dict = {}
        except Exception as e:
            print(f"WARNING: Unexpected error loading GVL '{self.gvl_filepath}': {e}. Vendor details lookup limited.")
            self.gvl_vendors_dict = {}

    def _load_cmp_list(self):
        """
        Internal method to load the CMP list data from the specified file path.
        Handles file not found and JSON decoding errors, storing results in instance attributes.
        Prints warnings on failure. Assumes CMP data is keyed by string CMP ID,
        potentially under a top-level 'cmps' key.
        """
        print(f"Attempting to load CMP list data from '{self.cmp_list_filepath}'...")
        try:
            with open(self.cmp_list_filepath, 'r', encoding='utf-8') as f:
                self.cmp_list_data = json.load(f)

            if isinstance(self.cmp_list_data, dict):
                 # Check if data is nested under 'cmps' key, otherwise assume root is the dict
                 potential_dict = self.cmp_list_data.get('cmps', self.cmp_list_data)
                 if isinstance(potential_dict, dict):
                     # Ensure keys are strings
                     self.cmp_list_dict = {str(k): v for k, v in potential_dict.items()}
                     print(f"Successfully loaded CMP list data. Found {len(self.cmp_list_dict)} CMPs.")
                 else:
                     print(f"WARNING: Expected a dictionary of CMPs in '{self.cmp_list_filepath}' (potentially under 'cmps' key), but found type {type(potential_dict)}.")
                     self.cmp_list_dict = {}
            else:
                 print(f"WARNING: CMP list file '{self.cmp_list_filepath}' does not contain a dictionary at the root.")
                 self.cmp_list_dict = {}

        except FileNotFoundError:
            print(f"WARNING: CMP list file '{self.cmp_list_filepath}' not found. CMP details lookup will fail.")
            self.cmp_list_dict = {}
        except json.JSONDecodeError:
            print(f"WARNING: Could not decode JSON from CMP list file '{self.cmp_list_filepath}'. Check format. CMP details lookup fail.")
            self.cmp_list_dict = {}
        except Exception as e:
            print(f"WARNING: Unexpected error loading CMP list '{self.cmp_list_filepath}': {e}. CMP details lookup fail.")
            self.cmp_list_dict = {}

    def _decode_tcf(self):
        """
        Internal method to decode the TCF consent string using iab_tcf.decode.
        Handles empty strings and decoding exceptions. Stores the result in
        self.consent_object and sets self.error_state on critical failure.
        """
        if not self.consent_string:
            # Consider this a critical error for most operations
            self.error_state = "Consent string is empty."
            print(f"ERROR: {self.error_state}")
            self.consent_object = None
            return

        print(f"\nAttempting to decode TCF string: '{self.consent_string[:50]}...'")
        try:
            # The core decoding step
            self.consent_object = decode(self.consent_string)
            print("Successfully decoded TCF string.")
        except Exception as e:
            # Catch general Exception as specific iab_tcf exceptions may not be importable
            self.error_state = f"Failed to decode TCF string: {e}"
            print(f"ERROR: {self.error_state}")
            self.consent_object = None # Ensure object is None on failure

    def _get_vendor_gvl_data(self, vendor_id: int) -> dict:
        """
        Internal helper to safely retrieve the GVL data dictionary for a specific vendor ID.

        Args:
            vendor_id (int): The integer vendor ID.

        Returns:
            dict: The vendor's data dictionary from the GVL, or an empty dictionary
                  if the GVL wasn't loaded or the vendor ID is not found.
        """
        if not self.gvl_vendors_dict:
            return {}
        # GVL keys are strings
        return self.gvl_vendors_dict.get(str(vendor_id), {})

    def _get_vendor_details(self, vendor_id: int) -> dict:
        """
        Internal helper to get a formatted dictionary of details for a single vendor ID,
        using data from the GVL. Uses the format requested by the user previously.

        Args:
            vendor_id (int): The integer vendor ID.

        Returns:
            dict: A dictionary containing formatted vendor details based on GVL data,
                  with defaults for missing fields or if the vendor/GVL is not found.
        """
        vendor_gvl_data = self._get_vendor_gvl_data(vendor_id)
        is_gvl_loaded = bool(self.gvl_vendors_dict) # Check if GVL dictionary has content

        # Determine name based on availability
        if not is_gvl_loaded:
            name = 'unknown (GVL not loaded)'
        elif not vendor_gvl_data:
            name = 'unknown (Not in GVL)'
        else:
            name = vendor_gvl_data.get('name', 'unknown')

        # Return structure based on user's requested format
        return {
            'id': vendor_gvl_data.get('id', vendor_id), # Prefer GVL ID, fallback to input ID
            'name': name,
            'purposes': vendor_gvl_data.get('purposes', []),
            'legIntPurposes': vendor_gvl_data.get('legIntPurposes', []),
            'flexiblePurposes': vendor_gvl_data.get('flexiblePurposes', []),
            'specialPurposes': vendor_gvl_data.get('specialPurposes', []),
            'features': vendor_gvl_data.get('features', []),
            'specialFeatures': vendor_gvl_data.get('specialFeatures', []),
            'policyUrl': vendor_gvl_data.get('policyUrl', ''),
            'cookieMaxAgeSeconds': vendor_gvl_data.get('cookieMaxAgeSeconds', None),
            'usesCookies': vendor_gvl_data.get('usesCookies', False),
            'cookieRefresh': vendor_gvl_data.get('cookieRefresh', False),
            'usesNonCookieAccess': vendor_gvl_data.get('usesNonCookieAccess', False),
            'deviceStorageDisclosureUrl': vendor_gvl_data.get('deviceStorageDisclosureUrl', '')
        }

    # --- Public Methods ---

    def get_metadata(self) -> dict:
        """
        Retrieves metadata from the decoded TCF consent string.

        Attempts to return metadata even if non-critical initialization errors occurred
        (e.g., file loading warnings). Includes an 'error' or 'initialization_error' key
        if applicable. Handles bytes and datetime objects for JSON serialization.

        Returns:
            dict: A dictionary containing TCF metadata (version, timestamps, CMP info, etc.).
                  Returns {'error': message} if decoding failed critically.
        """
        if not self.consent_object:
            msg = "Cannot get metadata, consent object not available (decoding may have failed)."
            print(f"Warning: {msg}")
            # Return error state if it exists, otherwise the generic message
            return {'error': self.error_state or msg}
        if self.error_state:
             print(f"Warning: Returning metadata, but a critical initialization error occurred: {self.error_state}")
             # Proceed to get what metadata we can, but include error info

        # Helper to safely get attributes, format dates, and decode bytes
        def _safe_get(attr_name):
            val = getattr(self.consent_object, attr_name, None)
            if isinstance(val, datetime):
                try:
                    # Use UTC timezone and ISO format
                    return val.astimezone(timezone.utc).isoformat()
                except (ValueError, OSError):
                    # Fallback for problematic timestamps (e.g., out of range)
                    return str(val)
            elif isinstance(val, bytes):
                try:
                    # Decode bytes using UTF-8, replace invalid chars
                    return val.decode('utf-8', errors='replace')
                except Exception as decode_err:
                     # Fallback if decoding fails
                    print(f"Warning: Could not decode bytes for attribute '{attr_name}': {decode_err}")
                    return f"<bytes: {len(val)} bytes>"
            # Return other types (int, bool, str, None) as is
            return val

        metadata = {
            'tcf_version': _safe_get('version'),
            'created': _safe_get('created'),
            'last_updated': _safe_get('last_updated'),
            'cmp_id': _safe_get('cmp_id'),
            'cmp_version': _safe_get('cmp_version'),
            'consent_screen': _safe_get('consent_screen'),
            'vendor_list_version': _safe_get('vendor_list_version'),
            'tcf_policy_version': _safe_get('tcf_policy_version'),
            'consent_language': _safe_get('consent_language'),
            'publisher_cc': _safe_get('publisher_cc'),
            'is_service_specific': _safe_get('is_service_specific'),
            'purpose_one_treatment': _safe_get('purpose_one_treatment'),
            'use_non_standard_stacks': _safe_get('use_non_standard_stacks')
            # Add other relevant fields from self.consent_object if needed
        }

        # Include initialization error in metadata if one occurred
        if self.error_state:
            metadata['initialization_error'] = self.error_state

        return metadata

    def get_consented_vendors(self, include_details: bool = True) -> list:
        """
        Gets the list of vendor IDs for which consent has been explicitly granted
        in the TCF string.

        Args:
            include_details (bool): If True (default), returns a list of dictionaries
                                    with full vendor details formatted via GVL lookup.
                                    If False, returns only a list of integer vendor IDs.

        Returns:
            list: A list of consented vendor IDs (int) or a list of vendor detail
                  dictionaries. Returns an empty list if decoding failed, no consent
                  object is available, or no vendors have consent.
        """
        if not self.consent_object or self.error_state:
            print("Warning: Cannot get consented vendors, consent object not available or init error.")
            return []
        # Check specifically for the attribute holding consent status
        if not hasattr(self.consent_object, 'consented_vendors'):
             print("Warning: Decoded consent object missing 'consented_vendors' attribute.")
             return []

        vendor_consents_dict = self.consent_object.consented_vendors
        # Filter for vendors where the value is True (consent granted)
        consented_vendor_ids = [
            vendor_id for vendor_id, consented in vendor_consents_dict.items() if consented
        ]

        if not consented_vendor_ids:
            print("No vendors found with consent in the TCF string.")
            return []

        if not include_details:
            # Return just the list of integer IDs
            return consented_vendor_ids
        else:
            # Return list of detailed dictionaries
            print(f"Building details for {len(consented_vendor_ids)} consented vendors...")
            details_list = [self._get_vendor_details(vid) for vid in consented_vendor_ids]
            return details_list

    def get_cmp_details(self) -> dict:
        """
        Retrieves details for the Consent Management Platform (CMP) identified
        in the TCF string by looking up its ID in the loaded CMP list data.

        Returns:
            dict: A dictionary containing the CMP's details directly from the
                  cmp-list.json file structure (if found). Includes an 'error' key
                  if the CMP ID is missing, the CMP list wasn't loaded, or the ID
                  was not found in the list. Returns {'id': id, 'name': 'unknown...'}
                  as a fallback structure on lookup failure.
        """
        if not self.consent_object:
            msg = "Cannot get CMP details, consent object not available."
            print(f"Warning: {msg}")
            return {'error': self.error_state or msg}
        if self.error_state:
             print(f"Warning: Attempting CMP details lookup, but init error occurred: {self.error_state}")

        if not hasattr(self.consent_object, 'cmp_id'):
            msg = "Consent object missing 'cmp_id' attribute."
            print(f"Warning: {msg}")
            return {'error': msg}

        cmp_id = getattr(self.consent_object, 'cmp_id', None) # Use getattr for safety
        if not cmp_id:
             # TCF spec allows CMP ID 0 or null, treat as "not set" for lookup purposes
             print("Warning: CMP ID is not set (0 or None) in the TCF string.")
             return {'id': cmp_id, 'name': 'unknown (CMP ID not set)'}

        # Check if CMP list was loaded
        if not self.cmp_list_dict:
            msg = "Cannot get CMP details, CMP list failed to load or is empty."
            print(f"Warning: {msg}")
            return {'id': cmp_id, 'name': 'unknown (CMP list not loaded)', 'error': msg}

        print(f"\nAttempting to find details for CMP ID: {cmp_id} in loaded CMP list...")
        cmp_id_str = str(cmp_id)
        # Retrieve the dictionary of CMP details from the loaded list
        cmp_details = self.cmp_list_dict.get(cmp_id_str)

        if cmp_details:
            print(f"  - Found details for CMP ID {cmp_id} in CMP list.")
            # Return the dictionary exactly as found in the CMP list file
            return cmp_details
        else:
            msg = f"CMP ID {cmp_id} not found in the loaded CMP list data."
            print(f"  - {msg}")
            # Return a consistent structure indicating lookup failure
            return {'id': cmp_id, 'name': 'unknown (Not found in CMP list)', 'error': msg}

    # --- Legitimate Interest Methods ---

    def get_vendors_using_legitimate_interest(self) -> dict:
        """
        Finds vendors for whom the user has established Legitimate Interest (LI)
        status via the TCF string.

        It checks the `legitimate_interest_vendors` map in the decoded consent object.
        For vendors where LI is established, it retrieves their name and the LI purposes
        they declare in the GVL (`legIntPurposes`).

        Returns:
            dict: A dictionary mapping vendor IDs (int) to details:
                  `{ vendor_id: {'name': str, 'declared_li_purposes': list[int]} }`
                  Returns empty dict if consent object unavailable, decoding failed,
                  the LI attribute is missing, or no vendors have LI established.
        """
        if not self.consent_object or self.error_state:
            print("Warning: Cannot get LI vendors, consent object not available or init error.")
            return {}
        if not hasattr(self.consent_object, 'legitimate_interest_vendors'):
            print("Warning: Decoded object missing 'legitimate_interest_vendors' attribute.")
            return {}

        li_vendors_dict = self.consent_object.legitimate_interest_vendors
        result = {}

        print(f"Checking {len(li_vendors_dict)} potential LI vendors...")
        for vendor_id, li_established in li_vendors_dict.items():
            # Check if LI is established (value is True)
            if li_established:
                vendor_gvl_data = self._get_vendor_gvl_data(vendor_id)
                declared_li_purposes = vendor_gvl_data.get('legIntPurposes', [])
                result[vendor_id] = {
                    'name': vendor_gvl_data.get('name', 'unknown'),
                    'declared_li_purposes': declared_li_purposes
                }

        print(f"Found {len(result)} vendors with Legitimate Interest established by user.")
        return result

    # --- Vendor Filtering Methods (Consent + GVL Declaration) ---

    def _get_consented_vendors_matching_gvl_list(self, gvl_list_key: str, required_ids: list[int], require_all: bool = False) -> dict:
        """
        Internal helper: Finds vendors who have consent (via TCF string) AND
        declare specific IDs in a given list within their GVL entry.

        Args:
            gvl_list_key (str): The key for the list attribute in the vendor's GVL data
                                (e.g., 'purposes', 'specialFeatures', 'legIntPurposes').
            required_ids (list[int]): A list of IDs (e.g., purpose IDs, feature IDs)
                                      to check for in the vendor's GVL list.
            require_all (bool): If True, the vendor must declare ALL IDs in `required_ids`
                                within their GVL list. If False (default), the vendor
                                must declare AT LEAST ONE ID from `required_ids`.

        Returns:
            dict: A dictionary mapping matching vendor IDs (int) to details:
                  `{ vendor_id: {'name': str, 'matched_ids': list[int]} }`
                  The 'matched_ids' list contains the subset of `required_ids` that
                  were actually found in the vendor's GVL declaration. Returns an
                  empty dictionary on error or if no vendors match.
        """
        if not self.consent_object or self.error_state:
            print(f"Warning: Cannot check vendors for GVL key '{gvl_list_key}', consent object unavailable or init error.")
            return {}
        if not hasattr(self.consent_object, 'consented_vendors'):
             print("Warning: Decoded object missing 'consented_vendors' attribute.")
             return {}

        consented_vendors_map = self.consent_object.consented_vendors
        matching_vendors = {}
        required_id_set = set(required_ids) # Use a set for efficient lookup

        if not required_id_set:
            print(f"Warning: No IDs provided to check for GVL key '{gvl_list_key}'.")
            return {}

        print(f"Checking consented vendors against GVL key '{gvl_list_key}' for IDs: {required_ids} (require_all={require_all})")
        # Iterate only through vendors who have consent
        for vendor_id, consented in consented_vendors_map.items():
            if consented:
                vendor_gvl_data = self._get_vendor_gvl_data(vendor_id)
                # Get the list of IDs declared by the vendor in GVL for the specific key
                declared_ids_list = vendor_gvl_data.get(gvl_list_key, [])
                declared_ids_set = set(declared_ids_list)

                # Find which of the required IDs are actually declared by this vendor
                intersection_ids = declared_ids_set.intersection(required_id_set)

                # Check if the requirement (all or at least one) is met
                passes_requirement = False
                if intersection_ids: # If there's any overlap
                    if require_all:
                        # Does the intersection contain all the required IDs?
                        if intersection_ids == required_id_set:
                             passes_requirement = True
                    else:
                        # If require_all is False, any intersection means success
                        passes_requirement = True

                if passes_requirement:
                    matching_vendors[vendor_id] = {
                        'name': vendor_gvl_data.get('name', 'unknown'),
                        # Store the specific required IDs that were matched
                        'matched_ids': sorted(list(intersection_ids))
                    }

        print(f"Found {len(matching_vendors)} consented vendors matching criteria for '{gvl_list_key}'.")
        return matching_vendors

    def get_consented_vendors_for_purposes(self, purpose_ids: list[int], require_all: bool = False) -> dict:
        """
        Finds vendors who have consent AND declare specific Purposes in the GVL.

        Note: This checks for vendor consent in the TCF string combined with the
        vendor's declaration in the GVL 'purposes' list. It does not strictly
        validate against the user's consented purposes list from the TCF string.

        Args:
            purpose_ids (list[int]): List of Purpose IDs to check for.
            require_all (bool): If True, vendor must declare ALL IDs. If False (default),
                                vendor must declare AT LEAST ONE ID.

        Returns:
            dict: `{ vendor_id: {'name': str, 'matched_ids': list[int]} }`
        """
        return self._get_consented_vendors_matching_gvl_list('purposes', purpose_ids, require_all)

    def get_consented_vendors_for_special_purposes(self, purpose_ids: list[int], require_all: bool = False) -> dict:
        """
        Finds vendors who have consent AND declare specific Special Purposes in the GVL.

        Args:
            purpose_ids (list[int]): List of Special Purpose IDs to check for.
            require_all (bool): If True, vendor must declare ALL IDs. If False (default),
                                vendor must declare AT LEAST ONE ID.

        Returns:
            dict: `{ vendor_id: {'name': str, 'matched_ids': list[int]} }`
        """
        return self._get_consented_vendors_matching_gvl_list('specialPurposes', purpose_ids, require_all)

    def get_consented_vendors_for_features(self, feature_ids: list[int], require_all: bool = False) -> dict:
        """
        Finds vendors who have consent AND declare specific Features in the GVL.

        Args:
            feature_ids (list[int]): List of Feature IDs to check for.
            require_all (bool): If True, vendor must declare ALL IDs. If False (default),
                                vendor must declare AT LEAST ONE ID.

        Returns:
            dict: `{ vendor_id: {'name': str, 'matched_ids': list[int]} }`
        """
        return self._get_consented_vendors_matching_gvl_list('features', feature_ids, require_all)

    def get_consented_vendors_for_special_features(self, feature_ids: list[int], require_all: bool = False) -> dict:
        """
        Finds vendors who have consent AND declare specific Special Features in the GVL.

        Note: This only checks vendor consent + GVL declaration. It doesn't validate
        against the user's Special Feature Opt-ins from the TCF string.

        Args:
            feature_ids (list[int]): List of Special Feature IDs to check for.
            require_all (bool): If True, vendor must declare ALL IDs. If False (default),
                                vendor must declare AT LEAST ONE ID.

        Returns:
            dict: `{ vendor_id: {'name': str, 'matched_ids': list[int]} }`
        """
        return self._get_consented_vendors_matching_gvl_list('specialFeatures', feature_ids, require_all)

    def get_consented_vendors_for_flexible_purposes(self, purpose_ids: list[int], require_all: bool = False) -> dict:
        """
        Finds vendors who have consent AND declare specific Flexible Purposes in the GVL.

        Note: The TCF allows flexible purposes to be satisfied by either consent or LI.
        This method specifically checks for vendors who have *consent* established in the
        TCF string and declare the purpose(s) under 'flexiblePurposes' in the GVL.

        Args:
            purpose_ids (list[int]): List of Flexible Purpose IDs to check for.
            require_all (bool): If True, vendor must declare ALL IDs. If False (default),
                                vendor must declare AT LEAST ONE ID.

        Returns:
            dict: `{ vendor_id: {'name': str, 'matched_ids': list[int]} }`
        """
        return self._get_consented_vendors_matching_gvl_list('flexiblePurposes', purpose_ids, require_all)

    # --- Vendor Property Lookup ---

    def get_vendor_urls(self, vendor_id: int) -> dict:
        """
        Retrieves the policy URL and device storage disclosure URL for a specific vendor ID
        directly from the loaded GVL data.

        Args:
            vendor_id (int): The integer ID of the vendor.

        Returns:
            dict: Contains 'policyUrl' (str), 'deviceStorageDisclosureUrl' (str).
                  Includes an 'error' key (str) if the GVL wasn't loaded or the vendor
                  ID was not found. URLs default to empty strings on failure.
        """
        if not self.gvl_vendors_dict:
             return {'policyUrl': '', 'deviceStorageDisclosureUrl': '', 'error': 'GVL not loaded or empty'}

        vendor_gvl_data = self._get_vendor_gvl_data(vendor_id)

        if not vendor_gvl_data:
            # Vendor ID not found in the loaded GVL dictionary
            return {'policyUrl': '', 'deviceStorageDisclosureUrl': '', 'error': f'Vendor ID {vendor_id} not found in GVL'}

        # Vendor found, return URLs using .get() for safety
        return {
            'policyUrl': vendor_gvl_data.get('policyUrl', ''),
            'deviceStorageDisclosureUrl': vendor_gvl_data.get('deviceStorageDisclosureUrl', '')
        }

    # --- Cookie / Non-Cookie Access Filtering ---

    def _get_consented_vendors_by_gvl_flag(self, gvl_flag_key: str) -> dict:
        """
        Internal helper: Finds vendors who have consent AND have a specific
        boolean flag set to true in their GVL entry.

        Args:
            gvl_flag_key (str): The key for the boolean flag in the vendor's GVL data
                                (e.g., 'usesCookies', 'usesNonCookieAccess').

        Returns:
            dict: A dictionary mapping matching vendor IDs (int) to their names (str).
                  Returns an empty dictionary on error or if no vendors match.
        """
        if not self.consent_object or self.error_state:
            print(f"Warning: Cannot check vendors for GVL flag '{gvl_flag_key}', consent object unavailable or init error.")
            return {}
        if not hasattr(self.consent_object, 'consented_vendors'):
             print("Warning: Decoded object missing 'consented_vendors' attribute.")
             return {}

        consented_vendors_map = self.consent_object.consented_vendors
        matching_vendors = {}

        print(f"Checking consented vendors for GVL flag '{gvl_flag_key}=true'...")
        # Iterate only through vendors who have consent
        for vendor_id, consented in consented_vendors_map.items():
            if consented:
                vendor_gvl_data = self._get_vendor_gvl_data(vendor_id)
                # Check if the flag exists and is True
                if vendor_gvl_data.get(gvl_flag_key, False): # Default to False if key missing
                    matching_vendors[vendor_id] = vendor_gvl_data.get('name', 'unknown')

        print(f"Found {len(matching_vendors)} consented vendors matching criteria for flag '{gvl_flag_key}'.")
        return matching_vendors

    def get_consented_vendors_using_cookies(self) -> dict:
        """
        Gets vendors who have consent AND declare 'usesCookies: true' in the GVL.

        Returns:
            dict: `{ vendor_id (int): name (str) }` for matching vendors.
        """
        return self._get_consented_vendors_by_gvl_flag('usesCookies')

    def get_consented_vendors_using_non_cookie_access(self) -> dict:
        """
        Gets vendors who have consent AND declare 'usesNonCookieAccess: true' in the GVL.

        Returns:
            dict: `{ vendor_id (int): name (str) }` for matching vendors.
        """
        return self._get_consented_vendors_by_gvl_flag('usesNonCookieAccess')


# --- Example Usage ---
if __name__ == "__main__":
    print("--- TCF Processor Example ---")

    # !!! --- Configuration --- !!!
    # !!! REPLACE THIS WITH YOUR ACTUAL TCF CONSENT STRING !!!
    # Sample string 1 (TCF v2)
    consent_string_to_test = "CQOKBEAQOKBEAAGABCENBgFgAP_gAEPgAApAJoMB5C5MQSFBIGJ0IJoAaAQFwBgAIAAgAgAAAYABQBIQAIwEQAECAACAAAACAAIAAAAAAABAEABAAAAAAAABAAAAAEAAAAAAAAAAAAAAAgBAAAAAAAAgUAAAAAAQAAQAgAAAQAIAQEgAAAAAAAAAAIAFAAAQAAAAAAAAQAAAAAAAgAgAkABAAAAAAAAAQBAAAAAAAAAAAIAAAAAEEZoFwAAYAFAAWABUAC4AHAAQAAkABUADIAGgAPQAfwBEAEUAJgATgAqgBvAD8AIQARwA5AB3ADxgIOAhABFACLAEiAJSAZwA2gB6gEyAKlAVYAtYBdAC8wGMgMkAZYA2gBuYDgAHLAQTAjMAWEgBgCtAHsA3MKALAAUACoAHoARQB4gEIAPUAugBjIDlgIzDoAYArQB7AP7HgCwAAgAKABUAD0AIoATgB4gHqAXQAxkCMxCASAAsAKoAbwB3AEUAJSAbQBVgD-yUAEAVpMAKAAEAzgC1gGMgOAKQAgBWgP7KgCAAAgAKABUAEUBawC6AGMgRmKAAQAtloAQA7gFWAAAA.f_gAAAAAAAAA"
    # Sample string 2 (TCF v2) - May have different consents/LI
    # consent_string_to_test = "CPzMBAAPzMBAAAvMCAAAAAAz5_______9______9uz_G________9____7_5___d_X__b____X71e_F7_6ff_3_4AAAAA"
    # Empty string example for error handling
    # consent_string_to_test = ""
    # Invalid string example for error handling
    # consent_string_to_test = "NOT_A_VALID_TCF_STRING"

    # Define file paths (make sure these files exist in the same directory or provide full paths)
    gvl_file_location = "vendor-list.json"
    cmp_list_file_location = "cmp-list.json"
    # !!! --- End Configuration --- !!!


    # 1. Create an instance of the processor
    # This automatically loads files and decodes the string
    print("\n1. Initializing TCFProcessor...")
    processor = TCFProcessor(
        consent_string=consent_string_to_test,
        gvl_filepath=gvl_file_location,
        cmp_list_filepath=cmp_list_file_location
    )
    print("-" * 25)

    # Check for critical errors during initialization (like TCF decoding failure)
    if processor.error_state:
        print(f"\nCRITICAL ERROR during initialization: {processor.error_state}")
        print("Further operations may fail or return incomplete data.")
        # Consider exiting if TCF decoding failed, as most methods depend on it
        if "decode" in processor.error_state.lower():
             print("Exiting due to TCF decoding failure.")
             exit(1)


    # 2. Get TCF Metadata
    print("\n2. TCF Metadata")
    print("-" * 25)
    metadata = processor.get_metadata()
    try:
        # Use default=str to handle potential lingering unserializable types as a fallback
        print(json.dumps(metadata, indent=2, default=str))
    except TypeError as e:
        print(f"ERROR serializing metadata to JSON: {e}\nRaw: {metadata}")
    print("-" * 25)


    # 3. Get Consented Vendors (List of IDs only)
    print("\n3. Consented Vendor IDs")
    print("-" * 25)
    vendor_ids = processor.get_consented_vendors(include_details=False)
    print(f"Found {len(vendor_ids)} consented vendor IDs.")
    print(vendor_ids[:20], "..." if len(vendor_ids) > 20 else "") # Print subset
    print("-" * 25)


    # 4. Get Consented Vendors (with Details from GVL)
    print("\n4. Consented Vendor Details (Sample)")
    print("-" * 25)
    vendor_details = processor.get_consented_vendors(include_details=True)
    if vendor_details:
         print(f"Showing details for first {min(5, len(vendor_details))} consented vendors:")
         try:
             print(json.dumps(vendor_details[:5], indent=2, default=str))
         except TypeError as e:
             print(f"ERROR serializing vendor details: {e}\nRaw: {vendor_details[:5]}")
         if len(vendor_details) > 5:
             print(f"  ... ({len(vendor_details) - 5} more vendors not shown)")
    else:
        print("No consented vendor details to display.")
    print("-" * 25)


    # 5. Get CMP Details (Using cmp-list.json)
    print("\n5. CMP Details")
    print("-" * 25)
    cmp_info = processor.get_cmp_details()
    try:
        print(json.dumps(cmp_info, indent=2, default=str))
    except TypeError as e:
        print(f"ERROR serializing CMP info: {e}\nRaw: {cmp_info}")
    print("-" * 25)


    # 6. Get LI Vendors
    print("\n6. Vendors with Legitimate Interest Established")
    print("-" * 25)
    li_vendors = processor.get_vendors_using_legitimate_interest()
    print(f"Total Count: {len(li_vendors)}")
    if li_vendors:
        # Print subset for brevity
        li_vendors_subset = {k: li_vendors[k] for k in list(li_vendors)[:5]}
        try:
            print(json.dumps(li_vendors_subset, indent=2, default=str))
            if len(li_vendors) > 5: print("...")
        except TypeError as e:
             print(f"ERROR serializing LI vendors: {e}\nRaw subset: {li_vendors_subset}")
    print("-" * 25)


    # 7. Get Vendors by Purpose / Feature Consent
    print("\n7. Vendors by Purpose/Feature (Examples)")
    print("-" * 25)
    # Example 1: Consented vendors declaring Purpose 1 (Store and/or access information)
    purpose_1_vendors = processor.get_consented_vendors_for_purposes([1])
    print(f"Consented Vendors declaring Purpose 1: Count={len(purpose_1_vendors)}")
    # print subset... (omitted for brevity)

    # Example 2: Consented vendors declaring Special Feature 1 (Use precise geolocation data)
    sp_feat_1_vendors = processor.get_consented_vendors_for_special_features([1])
    print(f"Consented Vendors declaring Special Feature 1: Count={len(sp_feat_1_vendors)}")
    # print subset...

    # Example 3: Consented vendors declaring BOTH Purpose 3 AND Purpose 4
    p3_p4_vendors = processor.get_consented_vendors_for_purposes([3, 4], require_all=True)
    print(f"Consented Vendors declaring BOTH Purposes 3 & 4: Count={len(p3_p4_vendors)}")
    # print subset...
    print("-" * 25)


    # 8. Get URLs for a specific Vendor
    print("\n8. URLs for Specific Vendor (e.g., ID 755)")
    print("-" * 25)
    vendor_id_to_check = 755 # Google
    urls = processor.get_vendor_urls(vendor_id_to_check)
    print(json.dumps(urls, indent=2))
    print("-" * 25)


    # 9. Get Vendors by Cookie/Non-Cookie Use
    print("\n9. Vendors by Cookie/Non-Cookie Use")
    print("-" * 25)
    cookie_vendors = processor.get_consented_vendors_using_cookies()
    print(f"Consented Vendors Using Cookies: Count={len(cookie_vendors)}")
    # print subset...

    non_cookie_vendors = processor.get_consented_vendors_using_non_cookie_access()
    print(f"Consented Vendors Using Non-Cookie Access: Count={len(non_cookie_vendors)}")
    # print subset...
    print("-" * 25)


    print("\n--- Script Finished ---")
import pefile
import pandas as pd

def extract_pe_features(path: str, feature_names: list[str]) -> pd.DataFrame:
    """
    Extracts a minimal PE feature set and aligns to model feature_names.
    Unknown/missing features are filled with 0 so predict() won't crash.
    """
    feats = {}
    try:
        pe = pefile.PE(path, fast_load=True)
        pe.parse_data_directories()
        # Common fields (many PE datasets include these; if not present, they’ll stay 0)
        feats.update({
            "Machine": getattr(pe.FILE_HEADER, "Machine", 0),
            "NumberOfSections": getattr(pe.FILE_HEADER, "NumberOfSections", 0),
            "MajorLinkerVersion": getattr(pe.OPTIONAL_HEADER, "MajorLinkerVersion", 0),
            "MinorLinkerVersion": getattr(pe.OPTIONAL_HEADER, "MinorLinkerVersion", 0),
            "MajorImageVersion": getattr(pe.OPTIONAL_HEADER, "MajorImageVersion", 0),
            "MajorOperatingSystemVersion": getattr(pe.OPTIONAL_HEADER, "MajorOperatingSystemVersion", 0),
            "SizeOfStackReserve": getattr(pe.OPTIONAL_HEADER, "SizeOfStackReserve", 0),
            "DllCharacteristics": getattr(pe.OPTIONAL_HEADER, "DllCharacteristics", 0),
            "SizeOfImage": getattr(pe.OPTIONAL_HEADER, "SizeOfImage", 0),
        })
        # You can add more fields if your PE dataset uses them.
    except Exception:
        pass

    # Align to expected columns
    row = {k: feats.get(k, 0) for k in feature_names}
    return pd.DataFrame([row])

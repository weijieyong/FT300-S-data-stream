"""Custom exceptions for FT300 sensor operations"""


class FT300Error(Exception):
    """Custom exception for FT300 sensor errors"""
    pass


class CRCError(FT300Error):
    """Exception raised when CRC validation fails"""
    pass

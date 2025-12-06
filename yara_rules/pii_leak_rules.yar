/*
 * YARA Rules for PII Leak Detection
 * Extracted from pii_leak_engine.py
 */

rule KR_ResidentRegistrationNumber
{
    meta:
        description = "Korean RRN"
        category = "PII"
    strings:
        $rrn1 = /[0-9]{6}-[1-4][0-9]{6}/
    condition:
        $rrn1
}

rule KR_PassportNumber
{
    meta:
        description = "Korean Passport Number"
        category = "PII"
    strings:
        $pass = /[A-Z][0-9]{8}/
    condition:
        $pass
}

rule KR_DriverLicenseNumber
{
    meta:
        description = "Korean Driver License Number"
        category = "PII"
    strings:
        $dl = /[0-9]{2}-[0-9]{2}-[0-9]{6}-[0-9]{2}/
    condition:
        $dl
}

rule KR_MobilePhone
{
    meta:
        description = "Korean Mobile Phone Number"
        category = "PII"
    strings:
        $phone1 = /010-[0-9]{4}-[0-9]{4}/
        $phone2 = /011-[0-9]{3,4}-[0-9]{4}/
        $phone3 = /016-[0-9]{3,4}-[0-9]{4}/
        $phone4 = /017-[0-9]{3,4}-[0-9]{4}/
        $phone5 = /018-[0-9]{3,4}-[0-9]{4}/
        $phone6 = /019-[0-9]{3,4}-[0-9]{4}/
    condition:
        any of them
}

rule Email_Address
{
    meta:
        description = "Generic Email Address"
        category = "PII"
    strings:
        $email = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/
    condition:
        $email
}

rule IPv4_Address
{
    meta:
        description = "IPv4 Address"
        category = "Network PII"
    strings:
        $ip = /[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/
    condition:
        $ip
}

rule US_SSN
{
    meta:
        description = "United States Social Security Number"
        category = "PII"
    strings:
        $ssn = /[0-9]{3}-[0-9]{2}-[0-9]{4}/
    condition:
        $ssn
}

rule Credit_Card_Number
{
    meta:
        description = "Credit Card Number (Visa/Mastercard/Amex/Discover)"
        category = "Financial PII"
    strings:
        $visa = /4[0-9]{15}/
        $visa_short = /4[0-9]{12}/
        $mc   = /5[1-5][0-9]{14}/
        $amex = /3[47][0-9]{13}/
        $disc = /6011[0-9]{12}/
        $disc2 = /65[0-9]{14}/
    condition:
        any of them
}

rule KR_BankAccount
{
    meta:
        description = "Korean Bank Account Number"
        category = "Financial PII"
    strings:
        $acct1 = /[0-9]{3}-[0-9]{2}-[0-9]{6}/
        $acct2 = /[0-9]{3}-[0-9]{3}-[0-9]{6}/
        $acct3 = /[0-9]{2}-[0-9]{6}-[0-9]{1}/
    condition:
        any of them
}

rule Medical_PHI
{
    meta:
        description = "Medical PHI Keyword Indicators"
        category = "Medical PII"
    strings:
        $patient = "Patient" nocase
        $diagnosis = "Diagnosis" nocase
        $medical = "Medical Record" nocase
        $prescription = "Prescription" nocase
        $doctor = "Doctor" nocase
        $clinic = "Clinic" nocase
    condition:
        any of them
}

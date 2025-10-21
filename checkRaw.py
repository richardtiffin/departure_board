from zeep import Client
from zeep.transports import Transport  # <- import Transport
from requests import Session
from requests.exceptions import HTTPError

WSDL_URL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01"
API_KEY = "c5dd7e87-7ae9-43fa-8add-cfe78ed0d00c"

# Build SOAP header
from zeep import xsd
AccessTokenHeader = xsd.Element(
    "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken",
    xsd.ComplexType([
        xsd.Element(
            "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue",
            xsd.String()
        )
    ])
)
header_value = AccessTokenHeader(TokenValue=API_KEY)

# Create Zeep client with custom transport
session = Session()
transport = Transport(session=session)
client = Client(wsdl=WSDL_URL, transport=transport)

# Make request with rate-limit detection
try:
    response = client.service.GetDepartureBoard(
        numRows=10,
        crs="CDF",
        _soapheaders=[header_value]
    )
    print("✅ SOAP call succeeded")
except HTTPError as e:
    if e.response.status_code == 429:
        print("💡 Rate limited! Wait before retrying.")
    else:
        print("HTTP ERROR:", e)
except Exception as e:
    # Catch other Zeep faults
    print("SOAP ERROR:", e)

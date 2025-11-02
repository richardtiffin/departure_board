from zeep import Client, xsd
from zeep.transports import Transport
from requests import Session
from requests.exceptions import HTTPError
import traceback
from zeep.helpers import serialize_object
from pprint import pprint

API_KEY = "be93d329-0050-4e75-84df-9c8c8cd6ee17"
WSDL_URL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01"

# Build SOAP header
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

# Session + Transport
session = Session()
transport = Transport(session=session, timeout=10)
client = Client(wsdl=WSDL_URL, transport=transport)

# Make request
try:
    response = client.service.GetDepartureBoard(
        numRows=100,
        crs="PAD",
        _soapheaders=[header_value]
    )
    # print("✅ SOAP call succeeded!")
    # if hasattr(response, "trainServices") and response.trainServices:
    #     for svc in response.trainServices.service[:3]:
    #         dest = svc.destination.location[0].locationName
    #         std = getattr(svc, "std", "?")
    #         etd = getattr(svc, "etd", "?")
    #         print(f"{std} → {dest} ({etd})")
    # else:
    #     print("No train services returned.")
except HTTPError as e:
    if e.response.status_code == 429:
        print("💡 Rate limited! Wait before retrying.")
    else:
        print("HTTP ERROR:", e)
except Exception as e:
    print("❌ SOAP ERROR:", e)
    traceback.print_exc()

response_dict = serialize_object(response)
for service in response_dict.get("trainServices", {}).get("service", []):
    if service.get("isCancelled") or str(service.get("etd", "")).lower() == "cancelled":
        print("🚫 Cancelled service found:")
        pprint(service)

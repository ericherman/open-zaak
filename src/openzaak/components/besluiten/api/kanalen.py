from vng_api_common.notifications.kanalen import Kanaal

from openzaak.components.besluiten.models import Besluit

KANAAL_BESLUITEN = Kanaal(
    "besluiten",
    main_resource=Besluit,
    kenmerken=("verantwoordelijke_organisatie", "besluittype"),
)

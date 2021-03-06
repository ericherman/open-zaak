import datetime
import uuid

from django.utils import timezone

import factory
import factory.fuzzy
from vng_api_common.constants import ObjectTypes, VertrouwelijkheidsAanduiding

from openzaak.components.catalogi.models.tests.factories import (
    InformatieObjectTypeFactory,
)


class EnkelvoudigInformatieObjectCanonicalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "documenten.EnkelvoudigInformatieObjectCanonical"

    latest_version = factory.RelatedFactory(
        "openzaak.components.documenten.models.tests.factories.EnkelvoudigInformatieObjectFactory",
        "canonical",
    )


class EnkelvoudigInformatieObjectFactory(factory.django.DjangoModelFactory):
    canonical = factory.SubFactory(
        EnkelvoudigInformatieObjectCanonicalFactory, latest_version=None
    )
    identificatie = uuid.uuid4().hex
    bronorganisatie = factory.Faker("ssn", locale="nl_NL")
    creatiedatum = datetime.date(2018, 6, 27)
    titel = "some titel"
    auteur = "some auteur"
    formaat = "some formaat"
    taal = "nld"
    inhoud = factory.django.FileField(data=b"some data", filename="file.bin")
    informatieobjecttype = factory.SubFactory(InformatieObjectTypeFactory)
    vertrouwelijkheidaanduiding = VertrouwelijkheidsAanduiding.openbaar

    class Meta:
        model = "documenten.EnkelvoudigInformatieObject"


class ObjectInformatieObjectFactory(factory.django.DjangoModelFactory):

    informatieobject = factory.SubFactory(EnkelvoudigInformatieObjectCanonicalFactory)
    object = factory.Faker("url")

    # class Meta:
    # model = 'documenten.ObjectInformatieObject'

    class Params:
        is_zaak = factory.Trait(
            object_type=ObjectTypes.zaak,
            object=factory.Sequence(lambda n: f"https://zrc.nl/api/v1/zaken/{n}"),
        )
        is_besluit = factory.Trait(
            object_type=ObjectTypes.besluit,
            object=factory.Sequence(lambda n: f"https://brc.nl/api/v1/besluiten/{n}"),
        )


class GebruiksrechtenFactory(factory.django.DjangoModelFactory):
    informatieobject = factory.SubFactory(EnkelvoudigInformatieObjectCanonicalFactory)
    omschrijving_voorwaarden = factory.Faker("paragraph")

    class Meta:
        model = "documenten.Gebruiksrechten"

    @factory.lazy_attribute
    def startdatum(self):
        return datetime.datetime.combine(
            self.informatieobject.latest_version.creatiedatum, datetime.time(0, 0)
        ).replace(tzinfo=timezone.utc)

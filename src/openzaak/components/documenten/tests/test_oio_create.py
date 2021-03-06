"""
Test filtering ZaakInformatieObject on Zaak.

See:
* https://github.com/VNG-Realisatie/gemma-zaken/issues/154 (us)
* https://github.com/VNG-Realisatie/gemma-zaken/issues/239 (mapping)
"""
from unittest import skip

from django.test import tag

from rest_framework import status
from rest_framework.test import APITestCase
from vng_api_common.tests import TypeCheckMixin

from openzaak.components.documenten.api.tests.utils import get_operation_url
from openzaak.components.documenten.models.tests.factories import (
    ObjectInformatieObjectFactory,
)
from openzaak.utils.tests import JWTAuthMixin

INFORMATIEOBJECTTYPE = (
    "https://example.com/ztc/api/v1/catalogus/1/informatieobjecttype/1"
)


@tag("oio")
@skip("OIO not implemented yet")
class US154Tests(TypeCheckMixin, JWTAuthMixin, APITestCase):
    heeft_alle_autorisaties = True

    def test_informatieobjecttype_filter(self):
        zaak_url = "http://www.example.com/zrc/api/v1/zaken/1"

        ObjectInformatieObjectFactory.create_batch(
            2,
            is_zaak=True,
            object=zaak_url,
            informatieobject__latest_version__informatieobjecttype=INFORMATIEOBJECTTYPE,
        )
        ObjectInformatieObjectFactory.create(
            is_zaak=True,
            object="http://www.example.com/zrc/api/v1/zaken/2",
            informatieobject__latest_version__informatieobjecttype=INFORMATIEOBJECTTYPE,
        )

        url = get_operation_url("objectinformatieobject_list")

        response = self.client.get(url, {"object": zaak_url})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())

        response_data = response.json()
        self.assertEqual(len(response_data), 2)

        for zio in response_data:
            self.assertEqual(zio["object"], zaak_url)

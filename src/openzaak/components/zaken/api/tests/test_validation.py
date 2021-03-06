import uuid
from unittest import skip
from unittest.mock import patch

from django.test import override_settings

from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APITestCase
from vng_api_common.constants import (
    Archiefnominatie,
    BrondatumArchiefprocedureAfleidingswijze,
    VertrouwelijkheidsAanduiding,
)
from vng_api_common.tests import get_validation_errors, reverse
from vng_api_common.validators import (
    IsImmutableValidator,
    ResourceValidator,
    URLValidator,
)
from zds_client.tests.mocks import mock_client

from openzaak.components.catalogi.models.tests.factories import (
    EigenschapFactory,
    ResultaatTypeFactory,
    StatusTypeFactory,
    ZaakInformatieobjectTypeFactory,
    ZaakTypeFactory,
)
from openzaak.components.documenten.models.tests.factories import (
    EnkelvoudigInformatieObjectFactory,
)
from openzaak.components.zaken.models import ZaakInformatieObject
from openzaak.components.zaken.models.constants import (
    AardZaakRelatie,
    BetalingsIndicatie,
)
from openzaak.components.zaken.models.tests.factories import (
    ResultaatFactory,
    StatusFactory,
    ZaakFactory,
    ZaakInformatieObjectFactory,
)
from openzaak.components.zaken.tests.utils import ZAAK_WRITE_KWARGS, isodatetime
from openzaak.utils.tests import JWTAuthMixin


class ZaakValidationTests(JWTAuthMixin, APITestCase):

    heeft_alle_autorisaties = True

    # Needed to pass Django's URLValidator, since the default APIClient domain
    # is not considered a valid URL by Django
    valid_testserver_url = "testserver.nl"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.zaaktype = ZaakTypeFactory.create()
        cls.zaaktype_url = reverse(cls.zaaktype)

    def test_validate_zaaktype_invalid(self):
        url = reverse("zaak-list")

        response = self.client.post(
            url,
            {
                "zaaktype": "https://example.com/foo/bar",
                "bronorganisatie": "517439943",
                "verantwoordelijkeOrganisatie": "517439943",
                "registratiedatum": "2018-06-11",
                "startdatum": "2018-06-11",
            },
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "zaaktype")
        self.assertEqual(validation_error["code"], "no_match")
        self.assertEqual(validation_error["name"], "zaaktype")

    def test_validate_zaaktype_valid(self, *mocks):
        url = reverse("zaak-list")

        response = self.client.post(
            url,
            {
                "zaaktype": f"http://testserver{self.zaaktype_url}",
                "vertrouwelijkheidaanduiding": VertrouwelijkheidsAanduiding.openbaar,
                "bronorganisatie": "517439943",
                "verantwoordelijkeOrganisatie": "517439943",
                "registratiedatum": "2018-06-11",
                "startdatum": "2018-06-11",
            },
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validation_camelcase(self):
        url = reverse("zaak-list")

        response = self.client.post(url, {}, **ZAAK_WRITE_KWARGS)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        bad_casing = get_validation_errors(response, "verantwoordelijke_organisatie")
        self.assertIsNone(bad_casing)

        good_casing = get_validation_errors(response, "verantwoordelijkeOrganisatie")
        self.assertIsNotNone(good_casing)

    def test_validate_communicatiekanaal_invalid_resource(self):
        url = reverse("zaak-list")
        body = {
            "communicatiekanaal": "https://ref.tst.vng.cloud/referentielijsten/api/v1/"
        }

        response = self.client.post(url, body, **ZAAK_WRITE_KWARGS)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = get_validation_errors(response, "communicatiekanaal")
        self.assertEqual(error["code"], ResourceValidator._ResourceValidator__code)

    @override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_404")
    def test_validate_communicatiekanaal_bad_url(self):
        url = reverse("zaak-list")
        body = {"communicatiekanaal": "https://someurlthatdoesntexist.com"}

        response = self.client.post(url, body, **ZAAK_WRITE_KWARGS)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = get_validation_errors(response, "communicatiekanaal")
        self.assertEqual(error["code"], URLValidator.code)

    def test_validate_communicatiekanaal_valid(self):
        url = reverse("zaak-list")
        body = {"communicatiekanaal": "https://example.com/dummy"}

        with override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_200"):
            with patch("vng_api_common.validators.obj_has_shape", return_value=True):
                response = self.client.post(url, body, **ZAAK_WRITE_KWARGS)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = get_validation_errors(response, "communicatiekanaal")
        self.assertIsNone(error)

    def test_relevante_andere_zaken_invalid(self):
        url = reverse("zaak-list")

        response = self.client.post(
            url,
            {
                "zaaktype": "https://example.com/foo/bar",
                "bronorganisatie": "517439943",
                "verantwoordelijkeOrganisatie": "517439943",
                "registratiedatum": "2018-06-11",
                "startdatum": "2018-06-11",
                "relevanteAndereZaken": [
                    {
                        "url": "https://example.com/andereZaak",
                        "aardRelatie": AardZaakRelatie.vervolg,
                    }
                ],
            },
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "relevanteAndereZaken.0.url")
        self.assertEqual(validation_error["code"], "no_match")

    def test_relevante_andere_zaken_valid_zaak_resource(self):
        url = reverse("zaak-list")

        zaak_body = {
            "zaaktype": f"http://testserver{self.zaaktype_url}",
            "bronorganisatie": "517439943",
            "verantwoordelijkeOrganisatie": "517439943",
            "registratiedatum": "2018-06-11",
            "startdatum": "2018-06-11",
            "vertrouwelijkheidaanduiding": VertrouwelijkheidsAanduiding.openbaar,
        }

        response = self.client.post(url, zaak_body, **ZAAK_WRITE_KWARGS)

        zaak2 = ZaakFactory.create()
        zaak2_url = reverse(zaak2)
        zaak_body.update(
            {
                "relevanteAndereZaken": [
                    {
                        "url": f"http://testserver{zaak2_url}",
                        "aardRelatie": AardZaakRelatie.vervolg,
                    }
                ]
            }
        )

        response = self.client.post(url, zaak_body, **ZAAK_WRITE_KWARGS)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_laatste_betaaldatum_betaalindicatie_nvt(self):
        """
        Assert that the field laatsteBetaaldatum may not be set for the NVT
        indication.
        """
        url = reverse("zaak-list")

        # all valid values
        for value in BetalingsIndicatie.values:
            if value == BetalingsIndicatie.nvt:
                continue
            with self.subTest(betalingsindicatie=value):
                response = self.client.post(
                    url,
                    {
                        "zaaktype": f"http://testserver{self.zaaktype_url}",
                        "vertrouwelijkheidaanduiding": VertrouwelijkheidsAanduiding.openbaar,
                        "bronorganisatie": "517439943",
                        "verantwoordelijkeOrganisatie": "517439943",
                        "registratiedatum": "2018-06-11",
                        "startdatum": "2018-06-11",
                        "betalingsindicatie": value,
                        "laatsteBetaaldatum": "2019-01-01T14:03:00Z",
                    },
                    **ZAAK_WRITE_KWARGS,
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # invalid value
        with self.subTest(betalingsindicatie=BetalingsIndicatie.nvt):
            response = self.client.post(
                url,
                {
                    "zaaktype": f"http://testserver{self.zaaktype_url}",
                    "vertrouwelijkheidaanduiding": VertrouwelijkheidsAanduiding.openbaar,
                    "bronorganisatie": "517439943",
                    "verantwoordelijkeOrganisatie": "517439943",
                    "registratiedatum": "2018-06-11",
                    "startdatum": "2018-06-11",
                    "betalingsindicatie": BetalingsIndicatie.nvt,
                    "laatsteBetaaldatum": "2019-01-01T14:03:00Z",
                },
                **ZAAK_WRITE_KWARGS,
            )

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            validation_error = get_validation_errors(response, "laatsteBetaaldatum")
            self.assertEqual(validation_error["code"], "betaling-nvt")

    def test_invalide_product_of_dienst(self):
        url = reverse("zaak-list")

        response = self.client.post(
            url,
            {
                "zaaktype": f"http://testserver{self.zaaktype_url}",
                "vertrouwelijkheidaanduiding": VertrouwelijkheidsAanduiding.openbaar,
                "bronorganisatie": "517439943",
                "verantwoordelijkeOrganisatie": "517439943",
                "registratiedatum": "2018-12-24",
                "startdatum": "2018-12-24",
                "productenOfDiensten": ["https://example.com/product/999"],
            },
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        validation_error = get_validation_errors(response, "productenOfDiensten")
        self.assertEqual(validation_error["code"], "invalid-products-services")

    @override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_404")
    def test_validate_selectielijstklasse_invalid_url(self):
        url = reverse("zaak-list")

        response = self.client.post(
            url,
            {
                "selectielijstklasse": "https://some-bad-url.com/bla",
                "zaaktype": "https://example.com/foo/bar",
                "bronorganisatie": "517439943",
                "verantwoordelijkeOrganisatie": "517439943",
                "registratiedatum": "2018-06-11",
                "startdatum": "2018-06-11",
            },
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "selectielijstklasse")
        self.assertEqual(validation_error["code"], "bad-url")

    @override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_200")
    def test_validate_selectielijstklasse_invalid_resource(self):
        url = reverse("zaak-list")
        responses = {"https://ztc.com/resultaten/1234": {"some": "incorrect property"}}

        with mock_client(responses):
            response = self.client.post(
                url,
                {
                    "selectielijstklasse": "https://ztc.com/resultaten/1234",
                    "zaaktype": f"http://testserver{self.zaaktype_url}",
                    "bronorganisatie": "517439943",
                    "verantwoordelijkeOrganisatie": "517439943",
                    "registratiedatum": "2018-06-11",
                    "startdatum": "2018-06-11",
                },
                **ZAAK_WRITE_KWARGS,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "selectielijstklasse")
        self.assertEqual(validation_error["code"], "invalid-resource")


class ZaakUpdateValidation(JWTAuthMixin, APITestCase):
    heeft_alle_autorisaties = True

    def test_validate_verlenging(self):
        """
        Regression test
        """
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)

        response = self.client.patch(
            zaak_url,
            {"verlenging": {"reden": "We hebben nog tijd genoeg", "duur": "P0Y1M0D"}},
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_validate_opschorting_indicatie_false(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)

        response = self.client.patch(
            zaak_url,
            {"opschorting": {"indicatie": False, "reden": ""}},
            **ZAAK_WRITE_KWARGS,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_validate_opschorting_required_fields_partial_update(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)

        response = self.client.patch(
            zaak_url, {"opschorting": {"wrongfield": "bla"}}, **ZAAK_WRITE_KWARGS
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        for field in ["opschorting.indicatie", "opschorting.reden"]:
            with self.subTest(field=field):
                error = get_validation_errors(response, field)
                self.assertEqual(error["code"], "required")

    def test_validate_verlenging_required_fields_partial_update(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)

        response = self.client.patch(
            zaak_url, {"verlenging": {"wrongfield": "bla"}}, **ZAAK_WRITE_KWARGS
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        for field in ["verlenging.reden", "verlenging.duur"]:
            with self.subTest(field=field):
                error = get_validation_errors(response, field)
                self.assertEqual(error["code"], "required")

    def test_not_allowed_to_change_zaaktype(self):
        zaak = ZaakFactory.create()
        url = reverse(zaak)
        zaaktype = ZaakTypeFactory.create()
        zaaktype_url = reverse(zaaktype)

        response = self.client.patch(
            url, {"zaaktype": f"http://testserver{zaaktype_url}"}, **ZAAK_WRITE_KWARGS
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        validation_error = get_validation_errors(response, "zaaktype")
        self.assertEqual(validation_error["code"], IsImmutableValidator.code)

    def test_not_allowed_to_change_identificatie(self):
        zaak = ZaakFactory.create(identificatie="gibberish")
        url = reverse(zaak)

        response = self.client.patch(
            url, {"identificatie": "new value"}, **ZAAK_WRITE_KWARGS
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        validation_error = get_validation_errors(response, "identificatie")
        self.assertEqual(validation_error["code"], IsImmutableValidator.code)


class DeelZaakValidationTests(JWTAuthMixin, APITestCase):

    heeft_alle_autorisaties = True

    def test_cannot_use_self_as_hoofdzaak(self):
        """
        Hoofdzaak moet een andere zaak zijn dan de deelzaak zelf.
        """
        zaak = ZaakFactory.create()
        detail_url = reverse(zaak)

        response = self.client.patch(
            detail_url, {"hoofdzaak": detail_url}, **ZAAK_WRITE_KWARGS
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = get_validation_errors(response, "hoofdzaak")
        self.assertEqual(error["code"], "self-forbidden")

    def test_cannot_have_multiple_levels(self):
        """
        Deelzaak kan enkel deelzaak zijn van hoofdzaak en niet andere deelzaken.
        """
        url = reverse("zaak-list")
        hoofdzaak = ZaakFactory.create()
        deelzaak = ZaakFactory.create(hoofdzaak=hoofdzaak)
        deelzaak_url = reverse(deelzaak)

        response = self.client.post(
            url, {"hoofdzaak": deelzaak_url}, **ZAAK_WRITE_KWARGS
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = get_validation_errors(response, "hoofdzaak")
        self.assertEqual(error["code"], "deelzaak-als-hoofdzaak")


class ZaakInformatieObjectValidationTests(JWTAuthMixin, APITestCase):

    heeft_alle_autorisaties = True

    def test_informatieobject_invalid(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)

        url = reverse(ZaakInformatieObject)

        response = self.client.post(
            url, {"zaak": zaak_url, "informatieobject": "https://drc.nl/api/v1"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "informatieobject")
        self.assertEqual(validation_error["code"], "no_match")
        self.assertEqual(validation_error["name"], "informatieobject")

    def test_informatieobject_no_zaaktype_informatieobjecttype_relation(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)
        io = EnkelvoudigInformatieObjectFactory.create()
        io_url = reverse(io)

        url = reverse(ZaakInformatieObject)

        response = self.client.post(
            url,
            {
                "zaak": f"http://testserver{zaak_url}",
                "informatieobject": f"http://testserver{io_url}",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "nonFieldErrors")
        self.assertEqual(
            validation_error["code"], "missing-zaaktype-informatieobjecttype-relation"
        )

    def test_informatieobject_create(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)
        io = EnkelvoudigInformatieObjectFactory.create(
            informatieobjecttype__concept=False
        )
        io_url = reverse(io)
        ZaakInformatieobjectTypeFactory.create(
            informatieobjecttype=io.informatieobjecttype, zaaktype=zaak.zaaktype
        )

        url = reverse(ZaakInformatieObject)

        response = self.client.post(
            url,
            {
                "zaak": f"http://testserver{zaak_url}",
                "informatieobject": f"http://testserver{io_url}",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class FilterValidationTests(JWTAuthMixin, APITestCase):
    """
    Test that incorrect filter usage results in HTTP 400.
    """

    heeft_alle_autorisaties = True

    def test_zaak_invalid_filters(self):
        url = reverse("zaak-list")

        invalid_filters = {"zaaktype": "123", "bronorganisatie": "123", "foo": "bar"}

        for key, value in invalid_filters.items():
            with self.subTest(query_param=key, value=value):
                response = self.client.get(url, {key: value}, **ZAAK_WRITE_KWARGS)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rol_invalid_filters(self):
        url = reverse("rol-list")

        invalid_filters = {
            "zaak": "123",  # must be a url
            "betrokkene": "123",  # must be a url
            "betrokkeneType": "not-a-valid-choice",  # must be a pre-defined choice
            "rolomschrijving": "not-a-valid-choice",  # must be a pre-defined choice
            "foo": "bar",
        }

        for key, value in invalid_filters.items():
            with self.subTest(query_param=key, value=value):
                response = self.client.get(url, {key: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_invalid_filters(self):
        url = reverse("status-list")

        invalid_filters = {
            "zaak": "123",  # must be a url
            "statustype": "123",  # must be a url
            "foo": "bar",
        }

        for key, value in invalid_filters.items():
            with self.subTest(query_param=key, value=value):
                response = self.client.get(url, {key: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StatusValidationTests(JWTAuthMixin, APITestCase):
    heeft_alle_autorisaties = True

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.zaaktype = ZaakTypeFactory.create()
        cls.statustype = StatusTypeFactory.create(zaaktype=cls.zaaktype)
        cls.statustype_end = StatusTypeFactory.create(zaaktype=cls.zaaktype)
        cls.zaaktype_url = reverse(cls.zaaktype)
        cls.statustype_url = reverse(cls.statustype)
        cls.statustype_end_url = reverse(cls.statustype_end)

    def test_not_allowed_to_change_statustype(self):
        _status = StatusFactory.create()
        url = reverse(_status)

        response = self.client.patch(
            url, {"statustype": "https://ander.statustype.nl/foo/bar"}
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_statustype_valid_resource(self):
        zaak = ZaakFactory.create(zaaktype=self.zaaktype)
        zaak_url = reverse(zaak)
        list_url = reverse("status-list")

        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "statustype": self.statustype_url,
                "datumStatusGezet": isodatetime(2018, 10, 1, 10, 00, 00),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_statustype_invalid_resource(self):
        zaak = ZaakFactory.create(zaaktype=self.zaaktype)
        zaak_url = reverse(zaak)
        list_url = reverse("status-list")

        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "statustype": "https://ander.statustype.nl/foo/bar",
                "datumStatusGezet": isodatetime(2018, 10, 1, 10, 00, 00),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        error = get_validation_errors(response, "statustype")
        self.assertEqual(error["code"], "no_match")

    def test_statustype_zaaktype_mismatch(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)
        list_url = reverse("status-list")

        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "statustype": self.statustype_url,
                "datumStatusGezet": isodatetime(2018, 10, 1, 10, 00, 00),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        error = get_validation_errors(response, "nonFieldErrors")
        self.assertEqual(error["code"], "zaaktype-mismatch")

    @freeze_time("2019-07-22T12:00:00")
    def test_status_datum_status_gezet_cannot_be_in_future(self):
        zaak = ZaakFactory.create(zaaktype=self.zaaktype)
        zaak_url = reverse(zaak)
        list_url = reverse("status-list")

        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "statustype": self.statustype_url,
                "datumStatusGezet": isodatetime(2019, 7, 22, 13, 00, 00),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "datumStatusGezet")
        self.assertEqual(validation_error["code"], "date-in-future")

    def test_status_with_informatieobject_lock(self):
        zaak = ZaakFactory.create(zaaktype=self.zaaktype)
        zaak_url = reverse(zaak)
        io = EnkelvoudigInformatieObjectFactory.create(canonical__lock=uuid.uuid4().hex)
        ZaakInformatieObjectFactory.create(zaak=zaak, informatieobject=io.canonical)
        resultaattype = ResultaatTypeFactory.create(
            archiefactietermijn="P10Y",
            archiefnominatie=Archiefnominatie.blijvend_bewaren,
            brondatum_archiefprocedure_afleidingswijze=BrondatumArchiefprocedureAfleidingswijze.afgehandeld,
            zaaktype=self.zaaktype,
        )
        ResultaatFactory.create(zaak=zaak, resultaattype=resultaattype)
        list_url = reverse("status-list")

        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "statustype": self.statustype_end_url,
                "datumStatusGezet": isodatetime(2019, 7, 22, 13, 00, 00),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "nonFieldErrors")
        self.assertEqual(validation_error["code"], "informatieobject-locked")

    def test_status_with_informatieobject_indicatie_gebruiksrecht_null(self):
        zaak = ZaakFactory.create(zaaktype=self.zaaktype)
        zaak_url = reverse(zaak)
        io = EnkelvoudigInformatieObjectFactory.create(indicatie_gebruiksrecht=None)
        ZaakInformatieObjectFactory.create(zaak=zaak, informatieobject=io.canonical)
        resultaattype = ResultaatTypeFactory.create(
            archiefactietermijn="P10Y",
            archiefnominatie=Archiefnominatie.blijvend_bewaren,
            brondatum_archiefprocedure_afleidingswijze=BrondatumArchiefprocedureAfleidingswijze.afgehandeld,
            zaaktype=self.zaaktype,
        )
        ResultaatFactory.create(zaak=zaak, resultaattype=resultaattype)
        list_url = reverse("status-list")

        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "statustype": self.statustype_end_url,
                "datumStatusGezet": isodatetime(2019, 7, 22, 13, 00, 00),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "nonFieldErrors")
        self.assertEqual(validation_error["code"], "indicatiegebruiksrecht-unset")


class ResultaatValidationTests(JWTAuthMixin, APITestCase):
    heeft_alle_autorisaties = True

    def test_not_allowed_to_change_resultaattype(self):
        resultaat = ResultaatFactory.create()
        url = reverse(resultaat)
        resultaattype = ResultaatTypeFactory.create()
        resultaattype_url = reverse(resultaattype)

        response = self.client.patch(
            url, {"resultaattype": f"http://testserver{resultaattype_url}"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        validation_error = get_validation_errors(response, "resultaattype")
        self.assertEqual(validation_error["code"], IsImmutableValidator.code)

    def test_resultaattype_invalid_resource(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse("zaak-detail", kwargs={"uuid": zaak.uuid})
        list_url = reverse("resultaat-list")

        response = self.client.post(
            list_url,
            {"zaak": zaak_url, "resultaattype": "https://ander.statustype.nl/foo/bar"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "resultaattype")
        self.assertEqual(validation_error["code"], "no_match")

    def test_resultaattype_incorrect_zaaktype(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse("zaak-detail", kwargs={"uuid": zaak.uuid})
        resultaattype = ResultaatTypeFactory.create()
        resultaattype_url = reverse(resultaattype)

        list_url = reverse("resultaat-list")

        response = self.client.post(
            list_url, {"zaak": zaak_url, "resultaattype": resultaattype_url}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "nonFieldErrors")
        self.assertEqual(validation_error["code"], "zaaktype-mismatch")


class KlantContactValidationTests(JWTAuthMixin, APITestCase):

    heeft_alle_autorisaties = True

    @freeze_time("2019-07-22T12:00:00")
    def test_klantcontact_datumtijd_not_in_future(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse("zaak-detail", kwargs={"uuid": zaak.uuid})
        list_url = reverse("klantcontact-list")

        response = self.client.post(
            list_url,
            {"zaak": zaak_url, "datumtijd": "2019-07-22T13:00:00", "kanaal": "test"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "datumtijd")
        self.assertEqual(validation_error["code"], "date-in-future")

    @skip("depends on permission class")
    def test_klantcontact_invalid_zaak(self):
        list_url = reverse("klantcontact-list")

        response = self.client.post(
            list_url,
            {
                "zaak": "some-wrong-value",
                "datumtijd": "2019-07-22T12:00:00",
                "kanaal": "test",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "zaak")
        self.assertEqual(validation_error["code"], "object-does-not-exist")


class ZaakEigenschapValidationTests(JWTAuthMixin, APITestCase):
    heeft_alle_autorisaties = True

    def test_create_eigenschap(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)
        eigenschap = EigenschapFactory.create()
        eigenschap_url = reverse(eigenschap)
        list_url = reverse("zaakeigenschap-list", kwargs={"zaak_uuid": zaak.uuid})

        response = self.client.post(
            list_url, {"zaak": zaak_url, "eigenschap": eigenschap_url, "waarde": "test"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_404")
    def test_eigenschap_invalid_url(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)

        list_url = reverse("zaakeigenschap-list", kwargs={"zaak_uuid": zaak.uuid})

        response = self.client.post(
            list_url, {"zaak": zaak_url, "eigenschap": "bla", "waarde": "test"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "eigenschap")
        self.assertEqual(validation_error["code"], "no_match")


class ZaakObjectValidationTests(JWTAuthMixin, APITestCase):
    heeft_alle_autorisaties = True

    @override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_200")
    def test_create_zaakobject(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)
        list_url = reverse("zaakobject-list")
        responses = {
            "http://some-api.com/objecten/1234": {
                "url": "http://some-api.com/objecten/1234"
            }
        }

        with mock_client(responses):
            response = self.client.post(
                list_url,
                {
                    "zaak": zaak_url,
                    "object": "http://some-api.com/objecten/1234",
                    "objectType": "adres",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    @override_settings(LINK_FETCHER="vng_api_common.mocks.link_fetcher_404")
    def test_create_zaakobject_invalid_url(self):
        zaak = ZaakFactory.create()
        zaak_url = reverse(zaak)
        list_url = reverse("zaakobject-list")
        response = self.client.post(
            list_url,
            {
                "zaak": zaak_url,
                "object": "http://some-api.com/objecten/1234",
                "objectType": "adres",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        validation_error = get_validation_errors(response, "object")
        self.assertEqual(validation_error["code"], "bad-url")

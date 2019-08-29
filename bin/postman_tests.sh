#!/bin/sh

test_platform_url=https://vng-test.maykin.nl

# TODO add url for NRC
# Download and execute the ZGW postman tests
wget https://vng-test.maykin.nl/api/v1/postman-test/get_version/ZGW_api_postman_tests/1.0.0/ -O tests.json
NODE_OPTIONS="--max-old-space-size=2048" node_modules/newman/bin/newman.js run tests.json \
    --env-var zrc_url=$test_platform_url/zaken/api/v1 \
    --env-var drc_url=$test_platform_url/documenten/api/v1 \
    --env-var ztc_url=$test_platform_url/catalogi/api/v1 \
    --env-var brc_url=$test_platform_url/besluiten/api/v1 \
    --env-var ac_url=$test_platform_url/autorisaties/api/v1 \
    --env-var referentielijst_url=https://referentielijsten-api.vng.cloud/api/v1 \
    --env-var mock_url=https://c9ac80e5-f4f6-46f9-9e64-a164c03b5f25.mock.pstmn.io \
    --env-var client_id=zgw_api_tests \
    --env-var secret=secret \
    --env-var client_id_limited=zgw_api_tests_limited \
    --env-var secret_limited=secret_limited \
    --timeout-request 5000

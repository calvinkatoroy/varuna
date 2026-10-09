def test_register_route_is_gone(api):
    assert api.post("/api/register", None, {"username": "x", "password": "Passw0rd!x"}).status_code in (404, 405)

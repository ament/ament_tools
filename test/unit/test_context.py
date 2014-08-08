from ament_tools import context


def test_context():
    c = context.Context()
    c.foo = 'bar'
    assert c.foo == 'bar'
    assert c['foo'] == 'bar'
    c['ping'] = 'pong'
    assert c.ping == 'pong'
    assert c['ping'] == 'pong'
    assert sorted(c.keys()) == sorted(['foo', 'ping'])

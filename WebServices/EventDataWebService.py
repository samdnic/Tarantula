import random
import string

import cherrypy

from PlaylistEvent import PlaylistEntry, DeviceTypes

events = [
    PlaylistEntry(10, "test", DeviceTypes.VIDEODEVICE, 1, "Test123", 4, 1, "", None, None, eventid=2),
    PlaylistEntry(10, "test", DeviceTypes.VIDEODEVICE, 1, "Test123", 4, 1, "", None, [PlaylistEntry(10, "test3"),], eventid=3)
]

class EventDataWebService(object):
    exposed = True

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    def GET(self):
        return [e.get_dict() for e in events]

    def POST(self, length=8):
        some_string = ''.join(random.sample(string.hexdigits, int(length)))
        cherrypy.session['mystring'] = some_string
        return some_string

    def PUT(self, another_string):
        cherrypy.session['mystring'] = another_string

    def DELETE(self):
        cherrypy.session.pop('mystring', None)

if __name__ == '__main__':
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        }
    }
    cherrypy.quickstart(EventDataWebService(), '/', conf)
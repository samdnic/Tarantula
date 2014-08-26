import cherrypy
import sqlalchemy.orm

from datatypes import PluginData

PLUGINDATASERVICE_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.db.on'     : True,
        }
    }

class PluginDataWebService(object):    
    exposed = True

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    def GET(self, instancename=None):
        """Return either a list of plugins, or a specific plugin"""
        if instancename != None:
            database = cherrypy.request.db
            
            try:
                dataarray = database.query(PluginData).filter(PluginData.instancename == instancename).one()
            except sqlalchemy.orm.exc.NoResultFound:
                raise cherrypy.HTTPError(404, "Plugin with name {0} not found".format(instancename))

            return dataarray.get_dict()
            
        else:                
            database = cherrypy.request.db

            dataarray = database.query(PluginData).all()
                                                                             
            return [e.get_dict() for e in dataarray]
            
if __name__ == '__main__':
    
    from SQLEngine import SAEnginePlugin, SATool
    SAEnginePlugin(cherrypy.engine, 'sqlite:///../datafiles/coredata.db').subscribe()
    cherrypy.tools.db = SATool()
    
    cherrypy.quickstart(PluginDataWebService(), '/', PLUGINDATASERVICE_CONF)
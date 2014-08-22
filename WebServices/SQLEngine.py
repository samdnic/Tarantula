# -*- coding: utf-8 -*-
import cherrypy
from cherrypy.process import plugins
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

"""Thanks to Sylvain Hellegouarch for originally posting this at http://www.defuze.org/archives/222-integrating-sqlalchemy-into-a-cherrypy-application.html"""
        
class SAEnginePlugin(plugins.SimplePlugin):
    def __init__(self, bus, connection_string=None):
        """
        The plugin is registered to the CherryPy engine and therefore
        is part of the bus (the engine *is* a bus) registery.
 
        We use this plugin to create the SA engine. At the same time,
        when the plugin starts we create the tables into the database
        using the mapped class of the global metadata.
        """
        plugins.SimplePlugin.__init__(self, bus)
        self.sa_engine = None
        self.connection_string = connection_string
        self.session = scoped_session(sessionmaker(autoflush=True,
                                                   autocommit=False))
 
    def start(self):
        self.bus.log('Starting up DB access')
        self.sa_engine = create_engine(self.connection_string, echo=False)
        self.bus.subscribe("bind-session", self.bind)
        self.bus.subscribe("commit-session", self.commit)
 
    def stop(self):
        self.bus.log('Stopping down DB access')
        self.bus.unsubscribe("bind-session", self.bind)
        self.bus.unsubscribe("commit-session", self.commit)
        if self.sa_engine:
            self.sa_engine.dispose()
            self.sa_engine = None
 
    def bind(self):
        """
        Whenever this plugin receives the 'bind-session' command, it applies
        this method and to bind the current session to the engine.

        It then returns the session to the caller.
        """
        self.session.configure(bind=self.sa_engine)
        return self.session

    def commit(self):
        """
        Commits the current transaction or rollbacks if an error occurs.

        In all cases, the current session is unbound and therefore
        not usable any longer.
        """
        try:
            self.session.commit()
        except:
            self.session.rollback()  
            raise
        finally:
            self.session.remove()
                    
class SATool(cherrypy.Tool):
    def __init__(self):
        """
        The SA tool is responsible for associating a SA session
        to the SA engine and attaching it to the current request.
        Since we are running in a multithreaded application,
        we use the scoped_session that will create a session
        on a per thread basis so that you don't worry about
        concurrency on the session object itself.
 
        This tools binds a session to the engine each time
        a requests starts and commits/rollbacks whenever
        the request terminates.
        """
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_session,
                               priority=20)
 
    def _setup(self):
        cherrypy.Tool._setup(self)
        cherrypy.request.hooks.attach('on_end_resource',
                                      self.commit_transaction,
                                      priority=80)
 
    def bind_session(self):
        """
        Attaches a session to the request's scope by requesting
        the SA plugin to bind a session to the SA engine.
        """
        session = cherrypy.engine.publish('bind-session').pop()
        cherrypy.request.db = session
 
    def commit_transaction(self):
        """
        Commits the current transaction or rolls back
        if an error occurs. Removes the session handle
        from the request's scope.
        """
        if not hasattr(cherrypy.request, 'db'):
            return
        cherrypy.request.db = None
        cherrypy.engine.publish('commit-session')
 
    
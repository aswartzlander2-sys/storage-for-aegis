"""Read-only route views. Servers have no independent domain or tunnel settings."""
import json
import time
from pathlib import Path

def routing_view(directory, state, now=None):
    now=time.time() if now is None else now
    routes={};fresh=False
    try:
        descriptor=json.loads((Path(directory)/'published-routes.json').read_text())
        if isinstance(descriptor,dict) and -30 <= now-float(descriptor.get('updated',0)) <= 90:
            fresh=True
            routes=descriptor.get('groups',{})
            if not isinstance(routes,dict): routes={}
    except (OSError,ValueError,TypeError):
        pass
    for group in state['groups']:
        group.setdefault('useDefaultTunnel',True)
        route=routes.get(group['id'])
        if group['useDefaultTunnel'] is False:
            expected='https://'+group.get('sub','')+'.'+group.get('base','')
            root_ok=isinstance(route,dict) and route.get('useDefaultTunnel') is False and route.get('rootDomain')==group.get('base') and route.get('base')==group.get('base')
            if not root_ok or (route.get('url') and route['url'].rstrip('/')!=expected) or (route.get('proposedUrl') and route['proposedUrl'].rstrip('/')!=expected):
                route={**(route if isinstance(route,dict) else {}),'state':'blocked','url':'','proposedUrl':'','detail':'Root-level routing has not been confirmed. Select the root domain and relaunch; no Burrow-prefixed fallback will be used.'}
        if isinstance(route,dict):
            ready=route.get('state')=='ready'
            try: ready=ready and -30<=now-float(route.get('checkedAt',0))<=90
            except (TypeError,ValueError):ready=False
            group.update(url=route.get('url','') if ready else '',proposedUrl=route.get('proposedUrl',''),routeState='ready' if ready else ('pending' if route.get('state')=='ready' else route.get('state','pending')),routeDetail=route.get('detail',''),routePort=route.get('port'),resolvedBase=route.get('base',''))
        elif group.get('routePort'):
            group.update(url='',routeState='missing' if fresh else 'pending',routeDetail='This group’s tunnel was removed. Launch the group to recreate it.' if fresh else 'Waiting for Burrow to refresh this group’s route.')
    groups={g['id']:g for g in state['groups']}
    for server in state['servers']:
        g=groups.get(server['group'],{})
        server['url']=g['url'].rstrip('/')+'/s/'+server['id']+'/' if g.get('url') and server.get('verified') and server.get('status')!='removed' else ''
        server['routeState']=g.get('routeState','not-published')
        server['inheritsGroupAddress']=True
    return state

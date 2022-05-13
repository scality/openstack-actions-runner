import logging

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi_utils.tasks import repeat_every

from web import redis_database, runner_m, github_manager, cloud_manager
from web.WebhookManager import WebHookManager
from web.models import WebHook
from runners_manager.monitoring.prometheus import prometheus_metrics, metrics

logger = logging.getLogger("runner_manager")
app = FastAPI()


app.add_route('/metrics', prometheus_metrics)


@app.on_event("startup")
@repeat_every(seconds=60 * 60)
def delete_orphan_runners():
    """
    Delete Virtual Machine if there are not tracked by the runner manager and
    Delete Github Runner if there are not tracked as well
    """
    logger.info("list not tracked VM")
    gh_runners = [elem['id'] for elem in github_manager.get_runners()['runners']]
    server_list = [runner for runner in cloud_manager.get_all_vms(github_manager.organization)]

    rd_runners = []
    for m in runner_m.runner_managers:
        rd_runners += m.get_runners().values()

    for server in server_list:
        if not next(filter(lambda r: r.vm_id == server.vm_id, rd_runners), None):
            logger.info(f'VM {server.vm_id} deleted')
            metrics.runner_vm_orphan_delete.inc()
            cloud_manager.delete_vm(server)

    for runner_id in gh_runners:
        if not next(filter(lambda r: r.action_id == runner_id, rd_runners), None):
            logger.info(f'self-hosted {runner_id} deleted')
            metrics.runner_github_orphan_delete.inc()
            github_manager.force_delete_runner(runner_id)


# TODO if we have multiple instances it might bug ?
@app.on_event("startup")
@repeat_every(seconds=60 * 2)
def refresh():
    logger.info("Refresh runners")
    try:
        runners = github_manager.get_runners()
        runner_m.update_all_runners(runners['runners'])
    except Exception as e:
        logger.info(e)


@app.on_event("startup")
@repeat_every(seconds=60 * 2)
def delete_images():
    cloud_manager.delete_images_from_shelved(f'runner-{github_manager.organization}')


@app.get("/")
async def root():
    """
    List redis database
    """
    keys = {}
    for elem in redis_database.redis.keys():
        keys[elem] = redis_database.redis.get(elem)

    return {"message": "Hello World", "redis_database": keys}


@app.post('/runners/refresh')
async def refresh_data():
    await refresh()
    return Response(status_code=200)


@app.post('/runners/reset')
async def reset_reset_runners(request: Request):
    """
    Delete Virutal machine and runner on githu and create new runner
    """
    g_runners = github_manager.get_runners()
    runner_m.update_all_runners(g_runners['runners'])
    runner_m.remove_all_runners()
    g_runners = github_manager.get_runners()
    runner_m.update_all_runners(g_runners['runners'])
    return Response(status_code=200)


@app.post('/webhook')
async def webhook_post(data: WebHook, request: Request):
    """
    Webhook point for Github
    """
    WebHookManager(payload=data, event=request.headers['X-Github-Event'])()
    return Response(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8080, debug=True, reload='/app/srcs')

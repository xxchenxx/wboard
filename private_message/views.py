import common, forms, models, __init__
from common import exceptions, utils
from models import PrivateMessage
from common.ajax_response import STATUS_SUCCESS
from django.http import HttpResponseRedirect, Http404
from datetime import datetime 
from django.db.models import Q
from django.views.decorators.cache import cache_page

@common.login_required
@common.method("POST")
@common.ajax_request
def history(request):
	id = request.POST.get('id', '')
	limit = int(request.POST.get('limit', 20))
	since_id = int(request.POST.get('since_id', 0))
	since_time = PrivateMessage.objects.get(id = since_id).created_time if since_id else datetime.now()
	print since_time
	if id:
		condition = ((Q(sender=request.user.id)&Q(receiver=id)) | \
		(Q(receiver=request.user.id)&Q(sender=id))) & \
		(Q(created_time__lt = since_time))
	else:
		condition = Q(receiver=request.user.id)&Q(has_read = False)
	query_set = PrivateMessage.objects.filter(condition)
	result = {'objects': [i.message(request.user) for i in query_set[:limit]]}
	utils.mark_read(PrivateMessage.objects.filter(condition))
	return result

#@cache_page(360)
@common.login_required
@common.method("GET")
@common.render_to("pm/chat.html")
def chat(request):
	return {}

#@cache_page(30)
@common.login_required
@common.ajax_by_method('pm/list.html')
def private_message_list(request):
	kind = request.GET.get('kind', '') or request.POST.get('kind', '')
	objects = PrivateMessage.objects.filter_messages(request.user, kind)
	if kind == 'all':
		utils.mark_read(objects)
		common.kv.ChannelKV(request.user).send_unread()
	user_id = request.GET.get('user_id', '') or request.POST.get('user_id', '')
	if user_id:
		objects = objects.filter(sender = user_id) + objects.filter(receiver = user_id)
	if not objects and request.method == 'GET':
		raise Http404	
	objects = utils.paginate_to_dict(objects, request)
	objects.update({'kind': kind})
	return objects

@common.login_required
@common.ajax_by_method('pm/detail.html')
def detail(request, pm_id):
	private_message = utils.get_object_by_id(PrivateMessage, pm_id, method = request.method)
	utils.verify_user(request, (private_message.sender, private_message.receiver))
	return {'private_message': private_message}
	
@common.method('POST')
@common.login_required
@common.ajax_request
def delete(request, pm_id):
	private_message = utils.get_object_by_id(PrivateMessage, pm_id)
	utils.verify_user(request, private_message.sender)
	private_message.delete()
	return {}
	
@common.login_required
#@common.csrf_protect
@common.render_to('pm/write.html')
def write_get(request):
	return {}

@common.login_required
@common.ajax_request
def write_post(request):
	form = forms.PrivateMessageForm(request.POST)
	if form.is_valid():
		for user in form.users_received:
			__init__.send_private_message_and_notify(
					request.user,
					user,
					form.cleaned_data['body_text'],
					form.attachments
			)
	else:
		raise exceptions.DataFieldMissed
	return {}
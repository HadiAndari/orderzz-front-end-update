from rest_framework.views import APIView
from fcm_django.models import FCMDevice
from rest_framework.response import Response
from datetime import datetime
from django.utils import timezone
class pushNotifications(APIView):
    def post(self, request):
        fcmToken = request.data["fcmToken"]
        oldFcmToken = request.data.get("oldFcmToken", None)
        if oldFcmToken:
            try:
                oldToken = FCMDevice.objects.get(registration_id=oldFcmToken)
                oldToken.delete()
            except FCMDevice.DoesNotExist:
                pass
    
        fcmDevice, created = FCMDevice.objects.get_or_create(
                registration_id=fcmToken,
                type="web"
            )
        
        if (created or not fcmDevice.name or not fcmDevice.user) and request.user.is_authenticated:
            fcmDevice.name = request.user.first_name
            fcmDevice.user = request.user
            fcmDevice.date_created = datetime.now(timezone.get_default_timezone())
            fcmDevice.save()
        elif not created:
            fcmDevice.date_created = datetime.now(timezone.get_default_timezone())
            fcmDevice.save()
   
        return Response("", 201)
        
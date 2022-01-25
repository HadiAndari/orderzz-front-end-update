

import json
from rest_framework.generics import UpdateAPIView, ListAPIView, RetrieveAPIView
from .Admin_panel_serializers import (OrderStatusSerializer,OrderDetailsSerializer)
from main.models import Order
from adminDashBoard.models import VendorBranch
from ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from collections import OrderedDict 
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.serializers import ValidationError
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_405_METHOD_NOT_ALLOWED
from .permissions import *
from django.db.models import Q
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import EmailMessage, BadHeaderError
from django.template.loader import render_to_string
from constance.backends.KeyValueDataBase import DatabaseBackend
from firebase_admin.messaging import Message, Notification
from fcm_django.models import FCMDevice
import fcm_django
class Tables_Pagination(LimitOffsetPagination):
    default_limit  = 10
    def paginate_queryset(self, queryset, request, pinnedOrdersCount , view=None, orderBy=None, navigate=False):
        self.count = self.get_count(queryset)
        self.limit  = self.get_limit(request)
        self.pinnedOrdersCount = pinnedOrdersCount
        if self.limit is None:
            return None
    
        self.offset  = self.get_offset(request)
    
        self.request = request
        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True

        if self.count == 0 or self.offset > self.count:
            return []
  
        if navigate:
            return list(queryset[self.offset:self.offset + self.limit])
  
        if orderBy[0] == '-':
            limit = self.count - (self.count - self.limit)
            offest = self.count  - self.offset
            queryset = queryset[0:offest]
            queryset = queryset[0:limit]
            return list(queryset)  
        else:
            return list(queryset[self.offset:self.offset + self.limit])


    def get_paginated_response(self, data):
        return OrderedDict([
            ('count', self.count + self.pinnedOrdersCount),
            ('results', data)
        ])


class Get_orders(ListAPIView):
   
    permission_classes =[vendor_Staff_Write_Permission]
    pagination_class = Tables_Pagination
    queryset = Order.objects.all()
    @method_decorator(ratelimit(key='ip', rate='2/s', method='GET'))
    def get(self, request):
        was_limited = getattr(request, 'limited', False)
        if was_limited:
            return Response(data={'key':'Too_many_requests'}, status=HTTP_405_METHOD_NOT_ALLOWED)
        paginator = self.pagination_class()
        formatedRequest = request.GET.copy()
        formatedRequest = dict(formatedRequest.lists())
        pinnedOrders = formatedRequest.pop('pinnedOrders', '')
        if not pinnedOrders:
            pinnedOrders = []
        else:
            pinnedOrders = pinnedOrders[0].split(',')
        
        try:
            formatedRequest.pop("limit")
            formatedRequest.pop("offset")
            init= bool(int(formatedRequest.pop("init")[0]))
            formatedRequest.pop("navigate")
            navigate = bool(int(request.GET.get('navigate')))
            for i,j in formatedRequest.items():
                formatedRequest[i] = j[0]
            scheduleTimeFilter = datetime.now(timezone.get_default_timezone()) + timedelta(hours=1)
            
            orderBy = formatedRequest.pop("order_by")
            orderDate__exact = formatedRequest.pop("orderDate__exact")
            formatedRequest.pop("branch")
            branch = request.GET['branch']
            pinnedOrdersQueryset = Order.objects.none()
            if init:
                pinnedOrdersQueryset = self.queryset.filter(pk__in=pinnedOrders).filter(orderDate__exact=orderDate__exact).filter(**formatedRequest).filter(branch__branchName = branch).values('orderTime','phoneNumber', 'id', 'orderStatus','firstName')
            
         
            queryset = self.queryset.exclude(pk__in=pinnedOrders).filter(**formatedRequest).filter(branch__branchName = branch).filter(Q(Q(schedule__lte=scheduleTimeFilter) & Q(schedule__date=orderDate__exact)  ) | Q( Q(schedule__exact=None) & Q(orderDate__exact=orderDate__exact))).order_by(orderBy).values('orderTime','phoneNumber', 'id', 'orderStatus','firstName')

            result_page = paginator.paginate_queryset(queryset, request, pinnedOrdersCount=len(pinnedOrders) ,orderBy=orderBy, navigate=navigate)
    
            d = paginator.get_paginated_response(data= list(pinnedOrdersQueryset) + result_page)
            
            return Response(d)
        except Exception as e:
            print(e.with_traceback())
            raise ValidationError()



   

class Get_order_details(RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderDetailsSerializer
    permission_classes =[vendor_Staff_Write_Permission]
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = Order.objects.prefetch_related('order__orderedItem').get(pk=request.GET.get('id'))
            serializer = self.get_serializer(instance)
            print(serializer.data["discountCard"])
       
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response("", HTTP_400_BAD_REQUEST)






class Change_order_status(UpdateAPIView):
    permission_classes = [vendor_Staff_Write_Permission]
    queryset = Order.objects.all()
    serializer_class = OrderStatusSerializer
    
    def get_notification_msg(self, orderStatus, userLanguage, rejectionReason):
  
        if orderStatus == "ACCEPTED":
            if userLanguage == "ar":
                return {"body":"تم قبول طلبك من قبل المطبخ ، وسيتم توصيله قريبًا", "title":"تم قبول الطلب"}
            return {"body":"Your order has been accepted by the kitchen, and will be delivered soon", "title":"Order accepted"}
        elif orderStatus == "INDELIVERY":
            if userLanguage == "ar":
                return {"body":"طلبك الآن في طريقه إليك. يجب أن تتلقى طلبك في أي وقت قريبًا", "title":"الطلب في طريقه"}
            return {"body":"Your order is now on its way. You should receive your order anytime soon","title":"Order in delivery"}
        elif orderStatus == "REJECTED":
            if userLanguage == "ar":
                return {"body": "نحن آسفون ، تم رفض طلبك. السبب: " + rejectionReason , "title":"تم رفض الطلب"}
            return {"body":"we are sorry, Your order has been rejected. Reason: " + rejectionReason, "title":"Order Rejected"}
        elif orderStatus == "CANCELLED":
            if userLanguage == "ar":
                return {"body":"تم إلغاء طلبك بنجاح", "title":"تم إلغاء الطلب"}
            return {"body":"Your order has been canceled successfully. ", "title":"Order cancelled"}
        elif orderStatus == "DELIVERED":
            if userLanguage == "ar":
                return {"body":"تم تسليم طلبك. وجبة هنيئة!", "title":"تم تسليم الطلب"}
            return  {"body":"Your order is delivered. Have a nice meal!", "title":"Order deliverd"}
   

    def sendOrderConfirmationEmail(self, orderID):
        ####
        vendorInfo = DatabaseBackend().mget(["Vendor_Name", "Delivery_Time","Vendor_Theme_Color"])
        vendorName = vendorInfo['Vendor_Name']
        mail_subject = f'Your {vendorName} order has been accepted.'

        
        orderInstance = Order.objects.prefetch_related('order__orderedItem').get(pk=orderID)
        vedorBranch = orderInstance.branch
        orderInstaceFullData = OrderDetailsSerializer(orderInstance).data
        words = vedorBranch.branchName.split(' ')
        orderID = [word[0] for word in words]
        orderID = "".join(orderID).upper() + '-' + str(orderInstaceFullData['id'])
     
        orderSchedule= None
        if orderInstaceFullData['schedule']:
            orderSchedule = datetime.strptime(orderInstaceFullData['schedule'], '%Y-%m-%d %H:%M:%S')
        message = render_to_string('order-confirmed.html', {
            'vendorName': vendorInfo['Vendor_Name'],
            'deliveryTime':vendorInfo['Delivery_Time'],
            'orderInstace':orderInstaceFullData,
            'homePageUrl':self.request.META['HTTP_ORIGIN'],
            'branchName':vedorBranch.branchName,
            'branchPhoneNumber':vedorBranch.phoneNumber,
            'invoiceTotal':orderInstaceFullData['subtotal'] + orderInstaceFullData['serviceFee'],
            'orderDateTime':datetime.strptime(orderInstaceFullData['orderDate'] + " " + orderInstaceFullData['orderTime'] , '%Y-%m-%d %H:%M:%S'),
            'orderSchedule':orderSchedule,
            'orderID':orderID,
            ###
            "primaryColor":vendorInfo["Vendor_Theme_Color"]
            

        })
        # # # Creating an HTML file
        Func = open("GFG-1.html","w", encoding="utf-8")
        
        # Adding input data to the HTML file
        Func.write(message)
                    
        # Saving the data into the HTML file
        Func.close()
        # print( message)
        return
        to_email = orderInstance.email
        email = EmailMessage( mail_subject, message, from_email="Chickenonfiretemplate@gmail.com", to=[to_email])
        
        try:
            email.send()
        except BadHeaderError:
            pass

    def update(self, request, *args, **kwargs):
     
        # try:
        partial = kwargs.pop('partial', False)
        instance = self.queryset.get(pk=request.GET.get('id'))
        oldOrderStatus = instance.orderStatus
        orderStatusACCEPTEDTime = instance.orderStatusACCEPTED

        serializer = self.serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        self.perform_update(serializer)

        # self.sendOrderConfirmationEmail(instance.pk)
        # if request.data["orderStatus"] == "ACCEPTED" and oldOrderStatus=="PENDING" and orderStatusACCEPTEDTime == None and instance.email != None:
        #     self.sendOrderConfirmationEmail(instance.pk)
    
        device = instance.fcmDevice
        
        if device:
            notificationMsg = self.get_notification_msg(instance.orderStatus,instance.userLanguage, instance.rejectionReason )
            device.send_message(Message(
                # notification=Notification(
                #     title = notificationMsg["title"], 
                #     body = notificationMsg["body"]
                # ),
                data={
                    "title" : notificationMsg["title"], 
                    "body" : notificationMsg["body"],
                    "Order ID": str(instance.pk),
                    "Type": "status",
                    "Status": instance.orderStatus,
                    "Rejection Reason": instance.rejectionReason,
                    "Cancelation Reason": instance.cancelationReason,
                    "language":instance.userLanguage,
                    "icon":"https://web-push-book.gauntface.com/demos/notification-examples/images/icon-512x512.png",
                     "image":"https://web-push-book.gauntface.com/demos/notification-examples/images/icon-512x512.png"
                    # "badge":"https://chickenonfire.orderzz.com/static/media/brand-logo_YYIngf3.png",
                    # "image":"/static/static/images/knet.png",
                    # "actions":json.dumps( [{
                    #     "action": 'atom-action',
                    #     "title": 'Atom',
                    #     "icon": '/static/static/images/knet.png'
                    # }])
                },

            ))
         

        return Response(serializer.data, HTTP_200_OK)

        # except Exception as e:
        #     print(e)
        #     return Response("", HTTP_400_BAD_REQUEST)
    



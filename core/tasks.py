@shared_task
def send_otp_email(email, otp):
    # Implement email sending logic
    pass

@shared_task
def schedule_booking_reminders(booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        booking_datetime = timezone.datetime.combine(
            booking.scheduled_date, 
            booking.scheduled_time
        )
        
        # Schedule 24h reminder
        reminder_24h = booking_datetime - timedelta(hours=24)
        if reminder_24h > timezone.now():
            send_booking_reminder.apply_async(
                args=[booking_id, '24h'],
                eta=reminder_24h
            )
        
        # Schedule 3h reminder
        reminder_3h = booking_datetime - timedelta(hours=3)
        if reminder_3h > timezone.now():
            send_booking_reminder.apply_async(
                args=[booking_id, '3h'],
                eta=reminder_3h
            )
        
        # Schedule 1h reminder
        reminder_1h = booking_datetime - timedelta(hours=1)
        if reminder_1h > timezone.now():
            send_booking_reminder.apply_async(
                args=[booking_id, '1h'],
                eta=reminder_1h
            )
    
    except Booking.DoesNotExist:
        pass

@shared_task
def send_booking_reminder(booking_id, reminder_type):
    try:
        booking = Booking.objects.get(id=booking_id)
        
        if booking.status != 'confirmed':
            return
        
        # Update reminder sent status
        if reminder_type == '24h':
            booking.reminder_24h_sent = True
        elif reminder_type == '3h':
            booking.reminder_3h_sent = True
        elif reminder_type == '1h':
            booking.reminder_1h_sent = True
        
        booking.save()
        
        # Send Firebase notification
        if booking.customer.firebase_uid:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f'Upcoming Appointment - {reminder_type} reminder',
                    body=f'Your {booking.service.name} appointment is in {reminder_type}.'
                ),
                token=booking.customer.firebase_uid,
                data={
                    'booking_id': str(booking.booking_id),
                    'type': 'booking_reminder'
                }
            )
            messaging.send(message)
    
    except Booking.DoesNotExist:
        pass

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Customer, Document, CylinderMovement
from django.core.exceptions import ObjectDoesNotExist
from .forms import DocumentForm, CustomerForm
from django.db.models import Sum
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch
from django.contrib import messages

@login_required
def dashboard(request):
    documents = None
    customer = None
    account_number = request.GET.get('account_number')
    total_holdings = None
    
    if account_number:
        try:
            customer = Customer.objects.get(account_number=account_number)
            # Always fetch all documents initially, ordered by date
            documents = Document.objects.filter(
                customer=customer
            ).prefetch_related('movements').order_by('-document_date')
            
            total_holdings = customer.get_total_holdings()
            print(f"Initial load: Found {documents.count()} documents for customer {customer.name}")
            
        except Customer.DoesNotExist:
            documents = []
            total_holdings = 0
    
    document_form = DocumentForm()
    return render(request, 'web/dashboard.html', {
        'documents': documents,
        'document_form': document_form,
        'account_number': account_number,
        'current_holdings': total_holdings,
        'customer': customer,
    })

@login_required
def customer_management(request):
    # Force a fresh query with no caching
    customers = Customer.objects.filter(is_active=True).order_by('name').select_related()
    
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            try:
                # Save the customer and force a database refresh
                customer = form.save(commit=False)
                customer.is_active = True
                customer.save()
                
                # Force a fresh query after saving
                updated_customers = Customer.objects.filter(
                    is_active=True
                ).order_by('name').select_related()
                
                # Return both success message and updated customer data
                return JsonResponse({
                    'success': True,
                    'message': f'Customer {customer.name} added successfully',
                    'customers': [
                        {
                            'account_number': c.account_number,
                            'name': c.name,
                            'contact_person': c.contact_person or '',
                            'phone_number': c.phone_number or '',
                            'total_holdings': c.get_total_holdings()
                        } for c in updated_customers
                    ]
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                })
    else:
        form = CustomerForm()
        # Force refresh customers list on GET request
        customers = Customer.objects.filter(
            is_active=True
        ).order_by('name').select_related()
    
    context = {
        'customers': customers,
        'form': form
    }
    
    return render(request, 'web/customer_management.html', context)

@login_required
def save_document(request):
    if request.method == 'POST':
        try:
            # Get customer
            customer = Customer.objects.get(account_number=request.POST.get('customer_account'))
            
            # Generate document number if not provided
            document_type = request.POST.get('document_type')
            document_number = request.POST.get('document_number')
            if not document_number:
                document_number = Document.generate_next_number(document_type)
            
            # Create document
            document = Document.objects.create(
                document_number=document_number,
                document_type=document_type,
                document_date=request.POST.get('document_date'),
                customer=customer,
                created_by=request.user,
                status='ACTIVE'
            )
            
            # Create movements
            if document_type == 'NR':
                # Only create returned movement for NR
                returned = request.POST.get('cylinders_returned')
                if returned and int(returned) > 0:
                    CylinderMovement.objects.create(
                        document=document,
                        movement_type='E',
                        quantity=int(returned)
                    )
            else:
                # Handle both movements for IN
                received = request.POST.get('cylinders_received')
                returned = request.POST.get('cylinders_returned')
                
                if received and int(received) > 0:
                    CylinderMovement.objects.create(
                        document=document,
                        movement_type='R',
                        quantity=int(received)
                    )
                
                if returned and int(returned) > 0:
                    CylinderMovement.objects.create(
                        document=document,
                        movement_type='E',
                        quantity=int(returned)
                    )
            
            return JsonResponse({
                'success': True,
                'message': 'Document saved successfully',
                'document': {
                    'id': document.id,
                    'document_number': document.document_number
                }
            })
            
        except Customer.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Customer not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })

def calculate_cylinder_holdings(customer, month=None):
    print(f"Calculating holdings for {customer.name}")  # Debug log
    
    # Get all movements ordered by date
    movements = CylinderMovement.objects.filter(
        document__customer=customer
    ).select_related('document').order_by('document__document_date')

    if month:
        year, month = month.split('-')
        end_date = timezone.datetime(int(year), int(month) + 1, 1)
        movements = movements.filter(document__document_date__lt=end_date)

    running_total = 0
    
    # Print all movements for debugging
    for movement in movements:
        print(f"\nDocument: {movement.document.document_number}")
        print(f"Date: {movement.document.document_date}")
        print(f"Type: {movement.movement_type}")
        print(f"Quantity: {movement.quantity}")
        
        if movement.movement_type == 'R':
            running_total += movement.quantity
        else:  # 'E' for Empty Return
            running_total -= movement.quantity
            
        print(f"Running total after this movement: {running_total}")

    print(f"\nFinal holdings: {running_total}")  # Debug log
    return running_total

@login_required
def get_customer_info(request):
    account_number = request.GET.get('account_number')
    print(f"Searching for customer with account number: {account_number}")
    
    try:
        customer = Customer.objects.get(account_number=account_number)
        print(f"Found customer: {customer.name}")
        
        # Get total holdings using the model method
        total_holdings = customer.get_total_holdings()
        print(f"Total holdings: {total_holdings}")
        
        return JsonResponse({
            'success': True,
            'customer': {
                'name': customer.name,
                'account_number': customer.account_number,
                'total_holdings': total_holdings,
                'contact_person': customer.contact_person,
                'phone_number': customer.phone_number,
                'email': customer.email
            }
        })
    except Customer.DoesNotExist:
        print(f"No customer found with account number: {account_number}")
        return JsonResponse({
            'success': False,
            'message': 'Customer not found'
        })
    except Exception as e:
        print(f"Error in get_customer_info: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@login_required
def get_customer_documents(request):
    account_number = request.GET.get('account_number')
    month_filter = request.GET.get('month', '')
    
    try:
        customer = Customer.objects.get(account_number=account_number)
        # Get all documents with a single query
        base_query = Document.objects.filter(
            customer=customer
        ).select_related(
            'customer'
        ).prefetch_related(
            'movements'
        ).order_by(
            '-document_date'
        )
        
        # Convert to list directly instead of using iterator
        all_documents = list(base_query)
        
        print("\nInitial query details:")
        print(f"Customer: {customer.name} ({customer.account_number})")
        print(f"Documents in database: {len(all_documents)}")
        
        # Debug print all documents
        for doc in all_documents:
            print(f"Found document: {doc.document_number}")
            print(f"  Date: {doc.document_date}")
            print(f"  Type: {doc.document_type}")
            print(f"  Status: {doc.status}")
            movements = list(doc.movements.all())
            print(f"  Movements: {len(movements)}")
            for m in movements:
                print(f"    {m.movement_type}: {m.quantity}")
            print("---")
        
        # Apply month filter if provided
        if month_filter and month_filter.strip():
            try:
                year, month = month_filter.split('-')
                year, month = int(year), int(month)
                documents = [
                    doc for doc in all_documents
                    if doc.document_date.year == year and doc.document_date.month == month
                ]
                print(f"\nFiltered for {year}-{month}: {len(documents)} documents")
            except ValueError:
                documents = all_documents
                print("\nInvalid month filter, using all documents")
        else:
            documents = all_documents
            print("\nNo month filter, using all documents")
        
        # Create document list for response
        document_list = []
        print("\nProcessing documents for response:")
        for doc in documents:
            # Calculate received and returned quantities
            received = sum(m.quantity for m in doc.movements.all() if m.movement_type == 'R')
            returned = sum(m.quantity for m in doc.movements.all() if m.movement_type == 'E')
            
            doc_data = {
                'id': doc.id,
                'document_number': doc.document_number,
                'document_type': doc.get_document_type_display(),
                'document_date': doc.document_date.strftime('%Y-%m-%d'),
                'received': received,
                'returned': returned
            }
            document_list.append(doc_data)
            print(f"Added to response: {doc.document_number} ({doc.document_date})")
        
        # Sort by date, newest first
        document_list.sort(key=lambda x: x['document_date'], reverse=True)
        
        response_data = {
            'success': True,
            'documents': document_list,
            'filter_applied': bool(month_filter and month_filter.strip()),
            'total_documents': len(document_list),
            'month_filter': month_filter if month_filter else 'none',
            'all_dates': sorted([doc['document_date'] for doc in document_list], reverse=True)
        }
        
        print("\nResponse Summary:")
        print(f"Total documents in response: {len(document_list)}")
        print("Document dates:", response_data['all_dates'])
        
        return JsonResponse(response_data)
        
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Customer not found'
        })
    except Exception as e:
        print(f"Error in get_customer_documents: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def check_document_number(request):
    doc_number = request.GET.get('document_number')
    exists = Document.objects.filter(document_number=doc_number).exists()
    return JsonResponse({
        'exists': exists
    })

@login_required
def get_document_details(request, document_number):
    try:
        document = Document.objects.get(document_number=document_number)
        received = document.movements.filter(movement_type='R').first()
        returned = document.movements.filter(movement_type='E').first()
        
        print(f"Found document: {document}")  # Debug log
        
        return JsonResponse({
            'success': True,
            'document': {
                'id': document.id,
                'document_number': document.document_number,
                'document_type': document.document_type,
                'document_date': document.document_date.strftime('%Y-%m-%d'),
                'customer_account': document.customer.account_number,
                'cylinders_received': received.quantity if received else None,
                'cylinders_returned': returned.quantity if returned else None,
                'customer_name': document.customer.name
            }
        })
    except Document.DoesNotExist:
        print(f"Document not found: {document_number}")  # Debug log
        return JsonResponse({
            'success': False,
            'message': 'Document not found'
        })
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug log
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
@staff_member_required
def update_document(request, document_id):
    try:
        document = Document.objects.get(id=document_id)
        
        if request.method == 'POST':
            # Update document fields
            document.document_date = request.POST.get('document_date')
            document.save()
            
            # Delete existing movements
            CylinderMovement.objects.filter(document=document).delete()
            
            # Create new movements based on document type
            if document.document_type == 'NR':
                # Only handle returned cylinders for NR
                returned = request.POST.get('cylinders_returned')
                if returned and int(returned) > 0:
                    CylinderMovement.objects.create(
                        document=document,
                        movement_type='E',
                        quantity=int(returned)
                    )
            else:
                # Handle both received and returned for IN
                received = request.POST.get('cylinders_received')
                returned = request.POST.get('cylinders_returned')
                
                if received and int(received) > 0:
                    CylinderMovement.objects.create(
                        document=document,
                        movement_type='R',
                        quantity=int(received)
                    )
                
                if returned and int(returned) > 0:
                    CylinderMovement.objects.create(
                        document=document,
                        movement_type='E',
                        quantity=int(returned)
                    )
            
            # Get updated document list
            updated_documents = Document.objects.filter(
                customer=document.customer
            ).prefetch_related('movements').order_by('-document_date')
            
            # Create document list for response
            document_list = []
            for doc in updated_documents:
                received = sum(m.quantity for m in doc.movements.all() if m.movement_type == 'R')
                returned = sum(m.quantity for m in doc.movements.all() if m.movement_type == 'E')
                
                document_list.append({
                    'id': doc.id,
                    'document_number': doc.document_number,
                    'document_type': doc.get_document_type_display(),
                    'document_date': doc.document_date.strftime('%Y-%m-%d'),
                    'received': received,
                    'returned': returned
                })
            
            return JsonResponse({
                'success': True,
                'message': f'Document {document.document_number} has been updated',
                'updated_documents': document_list
            })
            
    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Document not found'
        })
    except Exception as e:
        print(f"Error updating document: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error updating document: {str(e)}'
        })

@login_required
@staff_member_required
def delete_document(request, document_id):
    try:
        document = Document.objects.get(id=document_id)
        
        # Delete associated movements first
        CylinderMovement.objects.filter(document=document).delete()
        
        # Store document info for response
        document_info = {
            'number': document.document_number,
            'id': document.id
        }
        
        # Delete the document
        document.delete()
        
        # Get updated document list
        updated_documents = Document.objects.filter(
            customer=document.customer
        ).prefetch_related('movements').order_by('-document_date')
        
        # Create document list for response
        document_list = []
        for doc in updated_documents:
            received = sum(m.quantity for m in doc.movements.all() if m.movement_type == 'R')
            returned = sum(m.quantity for m in doc.movements.all() if m.movement_type == 'E')
            
            document_list.append({
                'id': doc.id,
                'document_number': doc.document_number,
                'document_type': doc.get_document_type_display(),
                'document_date': doc.document_date.strftime('%Y-%m-%d'),
                'received': received,
                'returned': returned
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Document {document_info["number"]} has been deleted',
            'deleted_document': document_info,
            'updated_documents': document_list
        })
    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Document not found'
        })
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error deleting document: {str(e)}'
        })

@login_required
def get_user_permissions(request):
    return JsonResponse({
        'is_admin': request.user.is_staff
    })

@login_required
def get_customer_details(request, account_number):
    try:
        customer = Customer.objects.get(account_number=account_number)
        # Get recent transactions
        recent_transactions = []
        for doc in customer.documents.order_by('-document_date')[:5]:
            received = doc.movements.filter(movement_type='R').first()
            returned = doc.movements.filter(movement_type='E').first()
            recent_transactions.append({
                'date': doc.document_date.strftime('%Y-%m-d'),
                'document_number': doc.document_number,
                'received': received.quantity if received else None,
                'returned': returned.quantity if returned else None
            })

        return JsonResponse({
            'success': True,
            'customer': {
                'name': customer.name,
                'account_number': customer.account_number,
                'contact_person': customer.contact_person,
                'phone_number': customer.phone_number,
                'email': customer.email,
                'total_holdings': customer.get_total_holdings(),
                'last_transaction': customer.documents.order_by('-document_date').first().document_date.strftime('%Y-%m-%d') if customer.documents.exists() else 'No transactions'
            },
            'recent_transactions': recent_transactions
        })
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Customer not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

def get_monthly_holdings(request):
    account_number = request.GET.get('account_number')
    year = request.GET.get('year', timezone.now().year)
    
    try:
        monthly_data = []
        
        # Filter by customer if account_number is provided, otherwise get all movements
        movements_query = CylinderMovement.objects.all()
        if account_number:
            try:
                customer = Customer.objects.get(account_number=account_number)
                movements_query = movements_query.filter(document__customer=customer)
                title = f"Monthly Cylinder Holdings for {customer.name}"
            except Customer.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Customer not found'
                })
        else:
            title = "Total Cylinder Holdings"

        # Calculate opening balance (all movements before the year)
        start_of_year = timezone.datetime(int(year), 1, 1)
        prior_movements = movements_query.filter(document__document_date__lt=start_of_year)
        prior_received = prior_movements.filter(movement_type='R').aggregate(Sum('quantity'))['quantity__sum'] or 0
        prior_returned = prior_movements.filter(movement_type='E').aggregate(Sum('quantity'))['quantity__sum'] or 0
        running_total = prior_received - prior_returned
        
        # Calculate for each month
        for month in range(1, 13):
            start_date = timezone.datetime(int(year), month, 1)
            if month == 12:
                end_date = timezone.datetime(int(year) + 1, 1, 1)
            else:
                end_date = timezone.datetime(int(year), month + 1, 1)
            
            # Get movements for this month
            month_movements = movements_query.filter(
                document__document_date__gte=start_date,
                document__document_date__lt=end_date
            )
            
            # Calculate month's movements
            month_received = month_movements.filter(movement_type='R').aggregate(Sum('quantity'))['quantity__sum'] or 0
            month_returned = month_movements.filter(movement_type='E').aggregate(Sum('quantity'))['quantity__sum'] or 0
            
            # Update running total
            running_total += (month_received - month_returned)
            
            monthly_data.append({
                'month': f"{year}-{str(month).zfill(2)}",
                'holdings': running_total
            })
            
            print(f"Month {month}: Received={month_received}, Returned={month_returned}, Total={running_total}")  # Debug log
        
        return JsonResponse({
            'success': True,
            'data': monthly_data,
            'title': title
        })
        
    except Exception as e:
        print(f"Error in get_monthly_holdings: {str(e)}")  # Debug log
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def get_monthly_holdings_report(request):
    report_date = request.GET.get('date')
    
    if not report_date:
        return JsonResponse({
            'success': False,
            'message': 'Date parameter is required'
        })
    
    try:
        report_date = timezone.datetime.strptime(report_date, '%Y-%m-%d').date()
        
        # Get all active customers
        customers = Customer.objects.filter(is_active=True)
        
        # Calculate holdings for each customer at specified date
        holdings_data = []
        for customer in customers:
            # Get all movements up to and including the specified date
            movements = CylinderMovement.objects.filter(
                document__customer=customer,
                document__document_date__lte=report_date
            )
            
            # Calculate total holdings
            received = movements.filter(movement_type='R').aggregate(Sum('quantity'))['quantity__sum'] or 0
            returned = movements.filter(movement_type='E').aggregate(Sum('quantity'))['quantity__sum'] or 0
            holdings = received - returned
            
            if holdings != 0:  # Only include customers with non-zero holdings
                holdings_data.append({
                    'account_number': customer.account_number,
                    'customer_name': customer.name,
                    'holdings': holdings,
                    'last_movement_date': customer.documents.filter(
                        document_date__lte=report_date
                    ).order_by('-document_date').values_list('document_date', flat=True).first()
                })
        
        # Sort by account number
        holdings_data.sort(key=lambda x: x['account_number'])
        
        return JsonResponse({
            'success': True,
            'report_date': report_date.strftime('%Y-%m-%d'),
            'data': holdings_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })



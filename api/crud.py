from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import extract
from .models import db, Category, Expense
from datetime import datetime
from sqlalchemy import func

# Define Blueprints
category_bp = Blueprint('category', __name__)
expense_bp = Blueprint('expense', __name__)

# ==========================================
# CATEGORY CRUD
# ==========================================

@category_bp.route('/', methods=['POST'])
@jwt_required()
def create_category():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    new_category = Category(
        category_name=data.get('category_name'),
        category_emoji=data.get('category_emoji'),
        user_id=user_id
    )
    db.session.add(new_category)
    db.session.commit()
    
    return jsonify(new_category.to_dict()), 201

@category_bp.route('/', methods=['GET'])
@jwt_required()
def get_categories():
    user_id = get_jwt_identity()
    # Only fetch active categories (soft delete implemented)
    categories = Category.query.filter_by(user_id=user_id, is_active=True).all()
    return jsonify([cat.to_dict() for cat in categories]), 200

@category_bp.route('/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_category(category_id):
    user_id = get_jwt_identity()
    category = Category.query.filter_by(category_id=category_id, user_id=user_id, is_active=True).first_or_404()
    
    data = request.get_json()
    category.category_name = data.get('category_name', category.category_name)
    category.category_emoji = data.get('category_emoji', category.category_emoji)
    
    db.session.commit()
    return jsonify(category.to_dict()), 200

@category_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    user_id = get_jwt_identity()
    category = Category.query.filter_by(category_id=category_id, user_id=user_id).first_or_404()
    
    # Soft delete: Hides the category but keeps historical expenses intact
    category.is_active = False
    db.session.commit()
    return jsonify({"message": "Category deleted successfully"}), 200


# ==========================================
# EXPENSE CRUD
# ==========================================

@expense_bp.route('/', methods=['POST'])
@jwt_required()
def create_expense():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Ensure the category belongs to the user and is active
    category_id = data.get('category_id')
    category = Category.query.filter_by(category_id=category_id, user_id=user_id, is_active=True).first()
    if not category:
        return jsonify({"error": "Invalid or inactive category"}), 400
        
    # Convert string date to Python date object
    date_obj = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
    
    new_expense = Expense(
        value=data.get('value'),
        date=date_obj,
        note=data.get('note', ''),
        category_id=category_id,
        user_id=user_id
    )
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify(new_expense.to_dict()), 201

@expense_bp.route('/', methods=['GET'])
@jwt_required()
def get_expenses():
    user_id = get_jwt_identity()
    
    # Extract query parameters for filtering
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    category_id = request.args.get('category_id', type=int)
    
    # Base query: Only this user's expenses
    query = Expense.query.filter_by(user_id=user_id)
    
    # Apply dynamic filters based on request arguments
    if year:
        query = query.filter(extract('year', Expense.date) == year)
    if month:
        query = query.filter(extract('month', Expense.date) == month)
    if category_id:
        query = query.filter_by(category_id=category_id)
        
    # Order by date descending (newest first)
    expenses = query.order_by(Expense.date.desc()).all()
    
    return jsonify([exp.to_dict() for exp in expenses]), 200

@expense_bp.route('/<int:expense_id>', methods=['PUT'])
@jwt_required()
def update_expense(expense_id):
    user_id = get_jwt_identity()
    expense = Expense.query.filter_by(expense_id=expense_id, user_id=user_id).first_or_404()
    
    data = request.get_json()
    if 'value' in data:
        expense.value = data['value']
    if 'date' in data:
        expense.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    if 'note' in data:
        expense.note = data['note']
    if 'category_id' in data:
        # Validate new category ownership
        category = Category.query.filter_by(category_id=data['category_id'], user_id=user_id, is_active=True).first()
        if category:
            expense.category_id = data['category_id']
            
    db.session.commit()
    return jsonify(expense.to_dict()), 200

@expense_bp.route('/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    user_id = get_jwt_identity()
    expense = Expense.query.filter_by(expense_id=expense_id, user_id=user_id).first_or_404()
    
    # Hard delete is fine for expenses (unlike categories)
    db.session.delete(expense)
    db.session.commit()
    return jsonify({"message": "Expense deleted successfully"}), 200

# ==========================================
# ANALYTICS / DONUT CHART
# ==========================================

@expense_bp.route('/analytics/donut', methods=['GET'])
@jwt_required()
def get_donut_chart_data():
    user_id = get_jwt_identity()
    
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    
    # Base query: Join Expense and Category, sum the values, group by Category
    query = db.session.query(
        Category.category_name,
        Category.category_emoji,
        func.sum(Expense.value).label('total_value')
    ).join(Expense, Expense.category_id == Category.category_id)\
     .filter(Expense.user_id == user_id)
    
    # Apply date filters if provided
    if year:
        query = query.filter(extract('year', Expense.date) == year)
    if month:
        query = query.filter(extract('month', Expense.date) == month)
        
    # Group by the category fields to get aggregate sums
    results = query.group_by(Category.category_name, Category.category_emoji).all()
    
    # Calculate the grand total for the timeframe
    grand_total = sum(row.total_value for row in results)
    
    # Format the data cleanly for the React frontend
    chart_data = []
    for row in results:
        # Convert total_value from BigInteger format to a standard int
        category_total = int(row.total_value) 
        percentage = round((category_total / grand_total) * 100, 2) if grand_total > 0 else 0
        
        chart_data.append({
            "category_name": row.category_name,
            "category_emoji": row.category_emoji,
            "total_value": category_total,
            "percentage": percentage
        })
        
    # Sort the chart data so the largest expenses appear first in the donut chart
    chart_data.sort(key=lambda x: x['total_value'], reverse=True)
    
    return jsonify({
        "grand_total": int(grand_total) if grand_total else 0,
        "chart_data": chart_data
    }), 200
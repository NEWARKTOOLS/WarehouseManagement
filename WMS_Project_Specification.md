# Warehouse Management System for Injection Moulding Company
## Comprehensive Project Specification for Claude Code

---

## PROJECT OVERVIEW

### Business Context
Small to medium injection moulding company with 7-10 Borche machines (80T-500T), producing approximately 500 SKUs. Operations run single shift (Monday-Thursday 7am-5pm) with lights-out production on weekends for simple parts. Currently using basic Google Sheets with no systematic tracking, requiring a complete digital transformation.

### Budget
£250 total project budget - requires efficient, open-source technology stack

### Primary Objectives
1. Implement real-time inventory tracking across multiple warehouse locations
2. Digitize production and order management
3. Enable mobile-first barcode scanning using workers' personal smartphones
4. Create foundation for quality control and ISO certification pathway
5. Integrate with Xero accounting system for order management
6. Provide actionable analytics and reporting for business insights

---

## TECHNICAL ARCHITECTURE

### Technology Stack (Recommended)
- **Backend Framework**: Python Flask or FastAPI (lightweight, free, excellent for small businesses)
- **Database**: SQLite for initial deployment (can migrate to PostgreSQL later if needed)
- **Frontend**: Progressive Web App (PWA) using HTML5, CSS3, JavaScript with responsive design
  - Frameworks: Bootstrap 5 or Tailwind CSS for mobile-first responsive design
  - Vanilla JavaScript or lightweight framework (Alpine.js or Vue.js)
- **Barcode Integration**: HTML5 Camera API + jsQR or QuaggaJS library (free, works on any smartphone)
- **Deployment**: Can run on local server or low-cost cloud hosting (£5-10/month VPS)
- **Reporting**: Chart.js or similar for dashboards
- **PDF Generation**: ReportLab (Python) or jsPDF for packing lists and labels

### Deployment Model
- **Web-based Progressive Web App (PWA)** - accessible via browser on desktop and mobile
- Can be "installed" on phones for app-like experience
- Offline capability for basic scanning operations
- Responsive design optimized for mobile phones (primary) and desktop (secondary)

### Integration Requirements
- **Xero API Integration**: Read/write access for orders, invoices, and customer data
- RESTful API architecture for future integrations
- Export capabilities: CSV, Excel, PDF

---

## CORE SYSTEM MODULES

### 1. WAREHOUSE & LOCATION MANAGEMENT

#### Location Hierarchy
```
SITE LEVEL
├── Container 1 (outdoor storage)
├── Container 2 (outdoor storage)
├── Outdoor Building (12m x 12m, high ceiling)
│   └── Racking System (with bay numbering)
└── Upstairs Warehouse (8m²)
    └── Rack Slots (row/bay/shelf system)
```

#### Location Features
- **Location Code System**: Automatically generate codes (e.g., CON1-P01, OUT-R01-B03-S02, UP-R05-B02-S01)
  - CON = Container, OUT = Outdoor Building, UP = Upstairs
  - P = Pallet position, R = Row, B = Bay, S = Shelf
- **Location Types**: Define characteristics (pallet storage, racking, bulk storage)
- **Capacity Tracking**: Track available space by location
- **Location Search**: Quick find by code or description
- **Visual Map** (future enhancement): Simple warehouse layout visualization

#### Implementation Notes
- Start with simple location codes, allow manual editing
- Provide bulk location creation tool
- Mobile scanning should show location info and current contents

---

### 2. INVENTORY MANAGEMENT

#### Material Types & Categories
1. **Raw Materials** (primarily outdoor storage)
   - Resins: PP, ABS, Acetal, and others (no PVC)
   - Storage: Typically 25kg bags on pallets
   - Location: Outdoor racking system
   
2. **Masterbatches & Additives** (upstairs storage)
   - Small containers (12kg boxes)
   - Location: Upstairs warehouse in designated area
   - Requires organized storage and easy access

3. **Finished Goods**
   - Small items: Upstairs rack slots
   - Large items: Outdoor building or containers
   - Categorize by size/weight for optimal storage

4. **Regrind Material**
   - Minimal tracking required (only for recycled job usage)
   - Simple quantity tracking without detailed traceability

#### Inventory Item Master Data
Each item should include:
- **Basic Info**: SKU, Description, Category, Unit of Measure
- **Physical Properties**: Weight, Dimensions, Color
- **Storage Info**: Default location, Min/Max levels, Reorder point
- **Material Specs** (for raw materials): Material grade, supplier, optional certificate storage
- **Production Info**: Associated mould(s), typical cycle time, parts per cycle
- **Images**: Upload product photos
- **Custom Fields**: Flexible for future needs

#### Stock Operations
1. **Stock Receipt**
   - Scan/enter item + quantity
   - Assign to location
   - Generate barcode labels
   - Record supplier, date, batch (optional)
   - Mobile-friendly interface

2. **Stock Movement**
   - Transfer between locations
   - Scan from-location and to-location
   - Update inventory in real-time
   - Record reason for move

3. **Stock Adjustment**
   - Physical count reconciliation
   - Damage/loss recording
   - Approval workflow for significant adjustments
   - Audit trail

4. **Stock Allocation**
   - Reserve stock for specific orders
   - Visual indication of allocated vs available
   - Auto-allocation suggestions

#### Barcode System
- **Barcode Generation**: System generates barcodes for all items
- **Barcode Types**: Code 128 (versatile, handles alphanumeric)
- **Label Printing**: 
  - PDF generation for standard A4 label sheets (Avery compatible)
  - Include: Barcode, SKU, Description, Location
  - Print from any device
- **Scanning**: Use smartphone cameras (no dedicated scanners needed)
- **Alternative Entry**: Manual SKU entry as backup

#### Stock Taking / Cycle Counting
- **Scheduled Counts**: Set up recurring count schedules
- **Location-Based**: Count by location (efficient for workers)
- **Variance Reports**: Highlight discrepancies
- **Adjustment Process**: Review and approve before updating system

---

### 3. PRODUCTION MANAGEMENT

#### Production Orders
- **Order Types**:
  - Make-to-Stock (replenishment)
  - Make-to-Order (customer specific)
- **Order Information**:
  - Order number (auto-generated)
  - Product SKU
  - Quantity required
  - Customer (if applicable)
  - Due date
  - Priority level
  - Status: Planned → In Progress → Completed → Delivered

#### Production Tracking (Basic Implementation)
- **Start Production**: Scan product code, select machine, confirm start
- **Complete Production**: Enter quantity produced, record any issues
- **Material Consumption**: Auto-calculate based on BOM (Bill of Materials)
- **Quick Status View**: See all active jobs at a glance

#### Setup Sheets & Production Parameters
- **Digital Setup Sheets**: Store for each product-mould combination
- **Information Stored**:
  - Mould number and configuration
  - Machine program number (reference to USB saved programs)
  - Temperature settings (barrel, mould)
  - Injection time/pressure
  - Cycle time (target)
  - Material specifications
  - Quality checkpoints
  - Photos of setup/first article
  - Notes/special instructions
- **Access**: Workers can view setup sheets on phone before starting job
- **Versioning**: Track changes to setup sheets over time

#### Machine Assignment
- **Machine List**: 7-10 Borche machines (80T-500T)
- **Machine Profiles**:
  - Machine ID/name
  - Tonnage
  - Current job
  - Status (running, idle, maintenance)
  - Performance metrics

---

### 4. MOULD MANAGEMENT

#### Mould Types
1. **Individual Moulds**: Standalone tools
2. **Family Moulds**: Use common bolster (Bolster 1, 2, 3, etc.) with interchangeable inserts

#### Mould Master Data
- **Identification**:
  - Mould number/code
  - Mould type (individual/family)
  - Bolster number (for family moulds)
  - Associated products (SKUs produced)
  
- **Technical Specifications**:
  - Tonnage requirement
  - Number of cavities
  - Cycle time (typical)
  - Material compatibility
  - Photos/drawings
  
- **Location**: Where mould is stored (on-site storage areas)

#### Mould Maintenance Tracking
- **Maintenance Schedule**:
  - Last PM (Preventive Maintenance) date
  - Next PM due date (e.g., every 12 months)
  - Alert system when PM overdue
  
- **Shot Counter** (future enhancement):
  - Track total shots
  - Maintenance intervals by shots
  
- **Maintenance Log**:
  - Date of maintenance
  - Type (PM, repair, modification)
  - Work performed
  - Technician notes
  - Photos of work
  
- **Issue Reporting**:
  - Moulders can flag issues via mobile app
  - Report problems: flash, short shots, ejection issues, etc.
  - Comments/notes attached to mould record
  - Creates maintenance task for toolroom

#### Mould Status
- Available
- In Use (on machine X)
- In Maintenance
- Awaiting Repair

---

### 5. ORDER & CUSTOMER MANAGEMENT

#### Customer Database
- Customer name, contact info, delivery addresses
- Credit terms, special requirements
- Order history and preferences
- Integration with Xero for financial data sync

#### Sales Orders (Integrated with Xero)
- **Create from Xero**: Pull new orders from Xero invoices
- **Order Details**:
  - Customer
  - Line items (products, quantities)
  - Delivery date
  - Delivery method (own van, haulage, collection, postal)
  - Special instructions
  
- **Order Status Tracking**:
  - New → In Production → Ready to Ship → Dispatched → Delivered
  - Update Xero status when order fulfilled
  
- **Stock Allocation**: Automatically allocate stock or create production orders

#### Delivery Management
- **Delivery Methods**:
  - Own van delivery (track driver, route)
  - Haulage company (record carrier, tracking number)
  - Customer collection (record collection date/time)
  - Postal service (track shipment)
  
- **JIT (Just-In-Time) Orders**:
  - Flag JIT customers
  - Priority in production scheduling
  - Delivery date management

#### Packing & Shipping
- **Packing List Generation**: Auto-generate from order
  - Customer details
  - Item list with quantities
  - Order number
  - Delivery address
  - PDF export and print
  
- **Label Generation**: Shipping labels with barcodes
  - Address labels
  - Product labels
  - Barcode labels for tracking

---

### 6. QUALITY CONTROL & TRACEABILITY

#### Lot/Batch Tracking (Foundation for Future ISO)
- **Batch Numbers**: Auto-generate unique batch codes
  - Format: YYMMDD-SKU-BATCH (e.g., 250128-PART001-001)
- **Batch Information**:
  - Product SKU
  - Production date
  - Machine used
  - Mould used
  - Operator
  - Material batch used
  - Quantity produced
  - Quality status (passed/hold/rejected)
  
- **Traceability Chain**:
  - Link batch to customer orders
  - Track material batch to finished batch
  - Recall capability: identify all affected orders

#### Quality Checkpoints (Basic Implementation)
- **First Article Inspection**: Record when job starts
  - Visual inspection
  - Dimension checks (optional fields)
  - Photo upload
  - Approve/reject
  
- **In-Process Checks** (future):
  - Scheduled checks during run
  - Record results
  - Flag issues
  
- **Final Inspection** (future):
  - Pre-shipping quality check
  - Certificate of Conformity generation

#### Quality Issue Logging
- **Non-Conformance Reports**:
  - Issue description
  - Product/batch affected
  - Root cause analysis (optional)
  - Corrective action
  - Status tracking
  - Photos
  
- **Return Management**:
  - Customer returns tracking
  - Reason codes
  - Disposition (rework, scrap, credit)

---

### 7. REPORTING & ANALYTICS

#### Real-Time Dashboard
Accessible on desktop and mobile, showing:

**Overview Metrics**:
- Current stock value
- Low stock alerts
- Active production orders
- Pending shipments
- Moulds due for maintenance

**Production Metrics**:
- Jobs completed today/week/month
- Production efficiency trends
- Machine utilization
- Downtime tracking

**Inventory Metrics**:
- Stock levels by category
- Stock movement trends
- Slow-moving items
- Fast-moving items (high runners)

**Visual Charts**:
- Production volume over time
- Top 10 products by quantity
- Material usage trends
- Order fulfillment rates

#### Standard Reports

1. **Inventory Reports**:
   - Stock on hand (by location, category, product)
   - Stock valuation
   - Low stock report
   - Aging inventory
   - Stock movement history
   
2. **Production Reports**:
   - Production summary (daily/weekly/monthly)
   - Jobs completed by product
   - Machine utilization
   - Efficiency trends
   - High runner analysis (identify top products)
   - Low volume analysis (products with decreasing mould time)
   
3. **Order Reports**:
   - Orders by status
   - Delivery performance
   - Customer order history
   - JIT fulfillment metrics
   
4. **Quality Reports**:
   - Non-conformance log
   - Batch traceability
   - Quality trends
   
5. **Mould Reports**:
   - Mould maintenance log
   - Overdue maintenance
   - Mould usage history
   - Issue frequency by mould

#### Predictive Analytics (Basic Implementation)
- **Demand Forecasting**:
  - Identify customer ordering patterns
  - Seasonal trends
  - Suggest proactive stock building
  - Alert when customer typically reorders
  
- **Stock Optimization**:
  - Recommend reorder points based on usage
  - Identify overstocked items
  - Suggest slow-mover actions

#### Export Capabilities
- All reports exportable to: CSV, Excel, PDF
- Scheduled email reports (future enhancement)

---

### 8. USER MANAGEMENT & SECURITY

#### Phase 1 (Current Budget):
- **Simple Login**: Username/password
- **Basic Roles**: Admin vs Worker
  - Admin: Full access
  - Worker: View inventory, scan operations, record production
  
#### Phase 2 (Future Enhancement - V2):
- **Advanced Permissions**:
  - Manager: Full access, reporting, settings
  - Supervisor: Production management, inventory adjustments
  - Operator: Scanning, production recording only
  - Warehouse Staff: Inventory operations only
  - Read-Only: View access for analysis
  
- **Activity Logging**: Track who did what and when

---

## USER INTERFACE DESIGN

### Mobile-First Design Principles
1. **Large Touch Targets**: Minimum 44x44px buttons
2. **Simplified Navigation**: Bottom navigation bar for key functions
3. **Quick Actions**: Common tasks accessible within 2 taps
4. **Camera Integration**: One-tap barcode scanning
5. **Offline Capability**: Cache recent data for use without internet
6. **Fast Loading**: Optimize for slower mobile connections

### Key Mobile Screens

#### Home/Dashboard (Mobile)
- Summary cards: Stock value, Active jobs, Alerts
- Quick action buttons:
  - Scan Barcode
  - Receive Stock
  - Start Production
  - Complete Job
  - View Inventory
- Recent activity feed

#### Barcode Scanning Screen
- Full-screen camera view
- Automatic scan detection
- Manual SKU entry option
- Last scanned items (quick re-scan)
- Context-aware: knows if you're receiving, moving, or picking

#### Inventory Search (Mobile)
- Search bar (by SKU, name, location)
- Filter by category/type
- Results list with:
  - Product image thumbnail
  - SKU and name
  - Quantity and location
  - Quick action buttons (move, adjust, view)

#### Production Interface (Mobile)
- Active jobs list
- Start job: Scan product → Select machine → Confirm
- Complete job: Enter quantity → Flag issues → Confirm
- View setup sheet: Full-screen readable format

### Desktop Interface

#### Navigation Structure
- **Top Bar**: Logo, Search, User menu, Notifications
- **Sidebar Menu**:
  - Dashboard
  - Inventory
  - Production
  - Orders
  - Moulds
  - Reports
  - Settings

#### Dashboard (Desktop)
- Multi-widget layout
- Drag-and-drop customization (future)
- Charts and graphs
- Quick filters and date ranges

#### Data Tables
- Sortable columns
- Advanced filtering
- Bulk actions
- Export options
- Responsive design (collapses on smaller screens)

---

## IMPLEMENTATION PHASES

### Phase 1: Core Foundation (Priority - within £250 budget)
**Target: 4-6 weeks development**

1. **Week 1-2: Setup & Core Infrastructure**
   - Database design and setup
   - User authentication
   - Basic UI framework (PWA structure)
   - Location management setup

2. **Week 3-4: Inventory Management**
   - Item master data
   - Stock receipt and movement
   - Barcode generation and scanning
   - Basic label printing
   - Stock search and reports

3. **Week 5: Production Basics**
   - Production order creation
   - Basic job tracking (start/stop)
   - Setup sheet storage
   - Machine assignment

4. **Week 6: Orders & Reporting**
   - Customer management
   - Order entry
   - Basic packing lists
   - Core reports and dashboard
   - Xero integration (basic)

**Phase 1 Deliverables**:
- Fully functional inventory system with barcode scanning
- Basic production tracking
- Order management
- Mobile-responsive interface
- Initial stock data migration from Google Sheets
- User training materials

### Phase 2: Enhanced Features (Future - separate budget)
**Estimated: £300-500 additional**

- Advanced quality control and batch tracking
- Mould maintenance scheduling and alerts
- Enhanced Xero integration (sync invoices, auto-updates)
- Advanced reporting and analytics
- Predictive demand forecasting
- Multi-user permissions
- Email notifications
- Advanced label designer
- Mobile app (native wrapper)

### Phase 3: ISO Preparation & Advanced Features (Future)
**Estimated: £500-1000 additional**

- Full quality management system
- Document management
- Certificate generation
- Audit trail enhancements
- Supplier quality management
- Advanced traceability
- Electronic signatures
- Automated workflows

---

## DATA MIGRATION STRATEGY

### Initial Stock Count
1. **Preparation**:
   - Set up all location codes first
   - Create product master data (import from Google Sheets)
   - Print location labels and barcode labels
   
2. **Physical Count Process**:
   - Count by location (systematic approach)
   - Use mobile app to record counts directly
   - Two-person teams (counter + scanner)
   - Reconcile counts before finalizing
   
3. **Go-Live**:
   - Complete count over weekend
   - System goes live Monday morning
   - Parallel run Google Sheets for 1 week as backup
   - Full transition after validation

### Data Import Tools
- CSV import for products
- CSV import for customers
- Bulk location creation
- Initial stock quantities import

---

## INTEGRATION SPECIFICATIONS

### Xero Integration
**API Requirements**:
- OAuth 2.0 authentication
- Read/write access to:
  - Contacts (customers)
  - Invoices (for order creation)
  - Items (product catalog sync)
  
**Sync Operations**:
- Manual sync trigger (initial phase)
- Pull new invoices → create orders
- Update invoice status when order fulfilled
- Optional: sync inventory quantities (future)

**Error Handling**:
- Log sync errors
- User notification of failures
- Retry mechanism

---

## TECHNICAL REQUIREMENTS

### System Requirements
**Server/Hosting**:
- Minimum: 2GB RAM, 20GB storage
- Linux-based (Ubuntu recommended)
- Python 3.9+
- SQLite database (can migrate to PostgreSQL if needed)
- Web server (Nginx or Apache)
- SSL certificate (for HTTPS - free via Let's Encrypt)

**Client Devices**:
- Smartphones: Any modern phone with camera (Android/iOS)
- Desktop: Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection: Required for real-time sync (offline mode for basic scanning)

### Performance Targets
- Page load time: <2 seconds on mobile
- Barcode scan response: <1 second
- Database queries: <500ms
- Support 10 concurrent users
- 100,000+ transactions per year

### Security
- HTTPS only (encrypted traffic)
- Password hashing (bcrypt)
- SQL injection protection (parameterized queries)
- XSS protection
- CSRF tokens
- Regular backups (daily, retained 30 days)
- Session timeout (30 minutes inactive)

### Backup & Recovery
- **Automated Backups**:
  - Daily full backup
  - Weekly off-site backup
  - 30-day retention
  
- **Recovery Procedures**:
  - Database restore process
  - Point-in-time recovery capability
  - Documented recovery time objective: <4 hours

---

## TESTING REQUIREMENTS

### Test Scenarios
1. **Inventory Operations**:
   - Receive stock with barcode generation
   - Move stock between locations
   - Scan barcode with camera
   - Stock adjustment workflow
   - Stock search and filtering
   
2. **Production**:
   - Create production order
   - Start job on machine
   - Complete job and update inventory
   - View setup sheet on mobile
   
3. **Orders**:
   - Create order manually
   - Generate packing list
   - Mark order as dispatched
   - Search order history
   
4. **Mobile Responsiveness**:
   - Test on various screen sizes
   - Portrait and landscape modes
   - Touch gesture support
   - Camera barcode scanning
   
5. **Integration**:
   - Xero authentication
   - Import orders from Xero
   - Sync customer data

### User Acceptance Testing
- Involve 2-3 workers in testing
- Test with real products and locations
- Document any usability issues
- Refine based on feedback

---

## TRAINING & DOCUMENTATION

### User Training (Included)
1. **Admin Training** (4 hours):
   - System overview
   - Setup and configuration
   - User management
   - Report generation
   - Troubleshooting
   
2. **Worker Training** (2 hours):
   - Mobile app navigation
   - Barcode scanning
   - Stock operations
   - Production recording
   - Common workflows

### Documentation Deliverables
1. **User Manual**:
   - Step-by-step instructions with screenshots
   - Common tasks quick reference
   - Mobile and desktop versions
   
2. **Admin Guide**:
   - System configuration
   - User management
   - Backup and maintenance
   - Troubleshooting guide
   
3. **Quick Reference Cards**:
   - Laminated cards for common tasks
   - Barcode scanning guide
   - Production workflow
   - Stock receipt process

---

## MAINTENANCE & SUPPORT

### Post-Launch Support (First 3 Months)
- Bug fixes (included)
- Email/phone support
- Minor usability adjustments
- Performance optimization

### Ongoing Maintenance (After 3 Months)
- Software updates
- Bug fixes
- Technical support
- Feature requests (quoted separately)
- Recommended: £50-100/month support retainer

### System Updates
- Security patches: Applied within 48 hours
- Feature updates: Quarterly releases
- Database optimization: Monthly
- Backup verification: Weekly

---

## SUCCESS METRICS

### Key Performance Indicators (KPIs)

**Inventory Accuracy**:
- Target: >95% accuracy within 3 months
- Measure: Monthly cycle counts

**Time Savings**:
- Target: 50% reduction in time spent searching for stock
- Target: 75% reduction in inventory count time

**Visibility**:
- Target: Real-time stock visibility
- Target: Same-day reporting capability

**Order Management**:
- Target: 100% order traceability
- Target: Reduce order errors by 80%

**Production Efficiency**:
- Target: Identify top 20% of high runners
- Target: 30% reduction in mould downtime through predictive maintenance

### ROI Projection
**Estimated Annual Savings**:
- Reduced stock search time: 5 hours/week × £20/hour = £5,200/year
- Faster inventory counts: 10 hours/month × £20/hour = £2,400/year
- Reduced stock-outs and overstocking: £3,000-5,000/year
- Better customer service (fewer errors): Intangible but significant

**Payback Period**: 1-2 months

---

## RISKS & MITIGATION

### Technical Risks
1. **Risk**: Smartphone camera scanning unreliable
   - **Mitigation**: Provide manual SKU entry as backup; lighting guidelines; test during UAT
   
2. **Risk**: Internet connectivity issues affecting operations
   - **Mitigation**: Implement offline mode for critical scanning operations; data syncs when online
   
3. **Risk**: Data migration errors
   - **Mitigation**: Thorough testing with sample data; parallel run period; data validation checks

### Adoption Risks
1. **Risk**: Worker resistance to new system
   - **Mitigation**: Involve workers in design feedback; comprehensive training; demonstrate time savings
   
2. **Risk**: Incomplete initial stock count
   - **Mitigation**: Phased approach; cycle counting to correct errors; accept initial inaccuracies
   
3. **Risk**: Scope creep beyond budget
   - **Mitigation**: Strict phase 1 feature lock; document future enhancements separately

### Business Risks
1. **Risk**: System downtime during critical operations
   - **Mitigation**: Host on reliable infrastructure; maintain backup procedures; paper backup process documented
   
2. **Risk**: Data loss
   - **Mitigation**: Automated daily backups; test restore procedures; off-site backup storage

---

## FUTURE ENHANCEMENT ROADMAP

### 6-12 Months
- Advanced user permissions
- Email notifications and alerts
- Enhanced Xero integration (automated sync)
- Customer portal (order status visibility)
- Advanced predictive analytics
- Native mobile apps (iOS/Android)

### 12-24 Months
- Full quality management system
- ISO 9001 documentation support
- Supplier management module
- Machine monitoring integration (IoT sensors)
- Advanced scheduling algorithms
- Multi-language support

### 24+ Months
- Integration with production monitoring systems
- Automated reordering (AI-driven)
- Advanced material traceability (blockchain)
- Augmented reality for warehouse navigation
- Voice-controlled operations

---

## PROJECT DELIVERABLES CHECKLIST

### Software Components
- [ ] Web application (backend + frontend)
- [ ] Progressive Web App functionality
- [ ] Database with schema and initial data
- [ ] Barcode scanning module
- [ ] Label generation system
- [ ] Reporting engine
- [ ] Xero integration
- [ ] Admin panel

### Documentation
- [ ] User manual (PDF)
- [ ] Admin guide (PDF)
- [ ] Quick reference cards (printable)
- [ ] System architecture document
- [ ] Database schema documentation
- [ ] API documentation (for integrations)

### Training Materials
- [ ] Training videos (screen recordings)
- [ ] Step-by-step guides with screenshots
- [ ] FAQ document
- [ ] Troubleshooting guide

### Deployment
- [ ] Production server setup
- [ ] SSL certificate installation
- [ ] Backup system configured
- [ ] Initial data import
- [ ] User accounts created

### Testing
- [ ] Test plan document
- [ ] UAT results document
- [ ] Bug tracking log
- [ ] Performance test results

---

## ACCEPTANCE CRITERIA

The system will be considered complete when:

1. **Core Functionality**:
   - ✅ All inventory operations work correctly (receive, move, adjust, search)
   - ✅ Barcode scanning works on at least 3 different smartphones
   - ✅ Stock levels update in real-time
   - ✅ Location system implemented and functional
   
2. **Production Management**:
   - ✅ Production orders can be created and tracked
   - ✅ Setup sheets can be stored and viewed on mobile
   - ✅ Machine assignment works correctly
   
3. **Order Management**:
   - ✅ Orders can be created and tracked through lifecycle
   - ✅ Packing lists generate correctly
   - ✅ Customer management functional
   
4. **Reporting**:
   - ✅ Dashboard displays with real-time data
   - ✅ All Phase 1 reports functional
   - ✅ Export to CSV/PDF works
   
5. **Mobile Experience**:
   - ✅ Responsive design works on phones and tablets
   - ✅ Camera scanning is smooth and reliable
   - ✅ Navigation is intuitive and fast
   
6. **Integration**:
   - ✅ Xero connection established and tested
   - ✅ Customer data syncs correctly
   
7. **Performance**:
   - ✅ Page loads in <2 seconds on mobile
   - ✅ Supports 10 concurrent users
   - ✅ No critical bugs
   
8. **Documentation & Training**:
   - ✅ All documentation delivered
   - ✅ Training sessions completed
   - ✅ Users can perform basic operations independently

---

## SPECIAL INSTRUCTIONS FOR CLAUDE CODE

### Development Priorities
1. **Mobile-first approach**: Design for small screens, scale up to desktop
2. **Keep it simple**: Don't over-engineer; functionality over fancy features
3. **Open-source everything**: Use free libraries and frameworks to stay within budget
4. **Performance matters**: Optimize for fast loading and smooth scanning
5. **Extensible design**: Build foundation that can grow with future phases

### Code Quality Standards
- Write clean, well-commented code
- Follow PEP 8 (Python) and standard JavaScript conventions
- Modular architecture for easy updates
- Error handling on all operations
- Logging for troubleshooting

### Testing Requirements
- Unit tests for critical functions
- Integration tests for Xero API
- Manual testing checklist provided
- Performance benchmarks documented

### Deployment Instructions
- Provide step-by-step deployment guide
- Include all dependencies in requirements.txt
- Environment variables documented
- Database migration scripts included

---

## GLOSSARY

**SKU**: Stock Keeping Unit - unique identifier for each product
**PWA**: Progressive Web App - web application that works like a native app
**JIT**: Just-In-Time - production/delivery system minimizing inventory
**PM**: Preventive Maintenance
**WIP**: Work In Progress
**BOM**: Bill of Materials - list of raw materials needed for a product
**Regrind**: Recycled plastic material from production waste
**Masterbatch**: Concentrated colorant or additive pellets
**Bolster**: Base plate of family mould that holds interchangeable inserts
**Cycle Time**: Duration from injection to ejection in moulding process
**Shot**: Single injection cycle of a moulding machine

---

## CONTACT & QUESTIONS

If you have questions during development:
- System architecture decisions
- Feature prioritization
- Technical implementation options
- Integration challenges
- Timeline adjustments

Please document and we can discuss before proceeding.

---

**Document Version**: 1.0
**Date**: January 28, 2026
**Project Budget**: £250
**Target Completion**: 6-8 weeks from start
**Created for**: Claude Code Development Assistant

---

END OF SPECIFICATION

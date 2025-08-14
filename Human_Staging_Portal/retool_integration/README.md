# Retool Integration Guide 🎨
**ReputeAI & Valentine Advisors - Human Staging Portal**

This guide shows how to integrate the Human Staging Portal with Retool using the official brand colors and design system.

## 🎨 Brand Color Implementation

### Core Brand Colors
Use these primary colors throughout your Retool interface:

- **Primary Orange**: `#fc5f36` - Main CTAs, brand elements
- **Light Orange**: `#fda790` - Highlights, secondary elements  
- **Dark Blue**: `#1c2d50` - Text, navigation, secondary buttons
- **Light Blue**: `#baccd8` - Soft accents, backgrounds
- **Deep Navy**: `#2C3E50` - Headers, strong contrast elements

### Status & Alert Colors
- **Success**: `#7FB069` (Sage Green) - Task completion, positive states
- **Warning**: `#F4D03F` (Warm Yellow) - Alerts, attention needed
- **Error**: `#C85450` (Soft Coral) - Failures, critical states
- **Info**: `#baccd8` (Light Blue) - Informational messages
- **Pending**: `#D2A3A9` (Dusty Rose) - In-progress states

## 🚀 Quick Setup Guide

### 1. Create New Retool App
1. Login to your Retool account
2. Create new app: "Human Staging Portal"
3. Set canvas background to: `#E8D5B7` (Warm Beige)

### 2. Configure API Resource
```javascript
// Resource Name: HumanPortalAPI
// Base URL: http://localhost:8001
// Headers: Content-Type: application/json
```

### 3. Core Queries Setup

#### Health Check Query
```javascript
// Query Name: health_check
// Resource: HumanPortalAPI
// Method: GET
// URL Params: /api/health
// Run: Automatically on page load
```

#### Get Next Task Query
```javascript
// Query Name: get_next_task  
// Resource: HumanPortalAPI
// Method: GET
// URL Params: /api/tasks/next?scraper_id={{scraper_select.value}}
// Trigger: Manual (button click)
```

#### Submit Task Query
```javascript
// Query Name: submit_task
// Resource: HumanPortalAPI  
// Method: POST
// URL Params: /api/tasks/submit
// Body: {
//   "task_id": "{{current_task.data.task.id}}",
//   "scraper_id": "{{scraper_select.value}}",
//   "headline": "{{headline_input.value}}",
//   "author": "{{author_input.value}}",
//   "body": "{{body_textarea.value}}",
//   "publication": "{{publication_input.value}}",
//   "date": "{{date_input.value}}",
//   "story_link": "{{link_input.value}}"
// }
```

#### Fail Task Query
```javascript
// Query Name: fail_task
// Resource: HumanPortalAPI
// Method: POST  
// URL Params: /api/tasks/fail
// Body: {
//   "task_id": "{{current_task.data.task.id}}",
//   "scraper_id": "{{scraper_select.value}}",
//   "error_message": "{{failure_reason.value}}"
// }
```

## 📱 Component Layout & Styling

### Header Section
**Container**: Full-width header
- **Background**: Linear gradient `#2C3E50` to `#1c2d50`
- **Padding**: 20px
- **Text Color**: `#ffffff`

```javascript
// Header Title Component
<Text>
  Content: "🚀 Human Staging Portal"
  Font Size: 24px
  Font Weight: 600
  Color: #ffffff
</Text>

// Subtitle Component  
<Text>
  Content: "ReputeAI & Valentine Advisors"
  Font Size: 14px
  Color: #baccd8
</Text>
```

### Dashboard Metrics
**Layout**: 3-column grid
- **System Health**: Display `{{health_check.data.status}}`
- **Available Tasks**: Display `{{health_check.data.tasks_available}}`
- **Current Scraper**: Dropdown for scraper selection

```javascript
// Metric Card Styling
Background: #ffffff
Border: 1px solid #808080  
Border Radius: 12px
Box Shadow: 0 4px 16px rgba(28, 45, 80, 0.1)
Padding: 20px

// Metric Value
Font Size: 32px
Font Weight: 700
Color: #fc5f36

// Metric Label  
Font Size: 12px
Color: #1c2d50
Text Transform: uppercase
```

### Task Assignment Section
**Get Next Task Button**:
```javascript
Background: linear-gradient(135deg, #fc5f36 0%, #fda790 100%)
Color: #ffffff
Border Radius: 8px
Padding: 12px 24px
Font Weight: 600
Box Shadow: 0 4px 12px rgba(252, 95, 54, 0.3)

// Hover State
Background: #e54f2c
Transform: translateY(-2px)
Box Shadow: 0 6px 16px rgba(252, 95, 54, 0.4)
```

### Current Task Display
**Task Card**:
```javascript
Background: #ffffff
Border Left: 4px solid #fc5f36
Border Radius: 0 8px 8px 0
Padding: 16px
Margin Bottom: 16px

// Task Title
Font Size: 18px
Font Weight: 600
Color: #2C3E50

// Task Meta
Font Size: 14px
Color: #A9A9A9
```

**Priority Badges**:
```javascript
// Urgent Priority
Background: #C85450
Color: #ffffff
Border Radius: 12px
Padding: 4px 12px
Font Size: 12px
Font Weight: 700

// High Priority  
Background: #fc5f36
Color: #ffffff

// Standard Priority
Background: #F4D03F
Color: #1c2d50

// Low Priority
Background: #A3C9A8
Color: #ffffff
```

### Content Extraction Form
**Form Container**:
```javascript
Background: #ffffff
Border Radius: 12px
Padding: 24px
Box Shadow: 0 4px 16px rgba(28, 45, 80, 0.1)

// Form Header
Background: linear-gradient(135deg, #fda790 0%, #F5E6A8 100%)
Margin: -24px -24px 24px -24px
Padding: 16px 24px
Border Radius: 12px 12px 0 0
Border Bottom: 2px solid #fc5f36
```

**Form Inputs**:
```javascript
Border: 2px solid #808080
Border Radius: 8px
Padding: 12px
Background: #ffffff
Color: #1c2d50

// Focus State
Border Color: #fc5f36
Box Shadow: 0 0 0 3px rgba(252, 95, 54, 0.1)
Outline: none

// Labels
Font Weight: 600
Color: #1c2d50
Margin Bottom: 8px
```

### Action Buttons
**Submit Button**:
```javascript
Background: #7FB069
Color: #ffffff
Border Radius: 8px
Padding: 12px 24px
Font Weight: 600

// Hover
Background: #6fa055
Transform: translateY(-2px)
```

**Fail Task Button**:
```javascript
Background: #C85450
Color: #ffffff
Border Radius: 8px
Padding: 12px 24px
Font Weight: 600

// Hover  
Background: #b44440
Transform: translateY(-2px)
```

**Open Article Button**:
```javascript
Background: linear-gradient(135deg, #2C3E50 0%, #1c2d50 100%)
Color: #ffffff
Border Radius: 8px
Padding: 12px 24px
Font Weight: 600

// Hover
Transform: translateY(-2px)
Box Shadow: 0 4px 12px rgba(28, 45, 80, 0.2)
```

## 🔄 Interactive Workflow

### 1. Dashboard Initialization
```javascript
// On page load
health_check.trigger()
available_tasks.trigger()

// Auto-refresh every 30 seconds
setInterval(() => {
  if (!current_task.data) {
    health_check.trigger()
    available_tasks.trigger()
  }
}, 30000)
```

### 2. Task Assignment Flow
```javascript
// Get Next Task Button Click
get_next_task.trigger().then(() => {
  if (get_next_task.data.success) {
    // Show task details
    current_task_container.setHidden(false)
    
    // Pre-populate form
    headline_input.setValue(get_next_task.data.task.title)
    publication_input.setValue(get_next_task.data.task.publication)
    link_input.setValue(get_next_task.data.task.permalink_url)
    
    // Enable action buttons
    submit_button.setDisabled(false)
    fail_button.setDisabled(false)
    open_article_button.setDisabled(false)
    
    // Show success message
    notification.showSuccess(`Task ${get_next_task.data.task.id} assigned!`)
  } else {
    notification.showInfo(get_next_task.data.message)
  }
})
```

### 3. Article Opening
```javascript
// Open Article Button Click
if (current_task.data?.task?.permalink_url) {
  utils.openUrl(current_task.data.task.permalink_url, '_blank')
  notification.showInfo('Article opened in new tab. Extract content and return here.')
} else {
  notification.showError('No article URL available.')
}
```

### 4. Content Submission
```javascript
// Submit Button Click
submit_task.trigger().then(() => {
  if (submit_task.data.success) {
    // Clear current task
    current_task_container.setHidden(true)
    
    // Reset form
    extraction_form.clearValue()
    
    // Disable buttons
    submit_button.setDisabled(true)
    fail_button.setDisabled(true)
    open_article_button.setDisabled(true)
    
    // Refresh dashboard
    health_check.trigger()
    available_tasks.trigger()
    
    // Show success
    notification.showSuccess(`Task submitted successfully!`)
  } else {
    notification.showError('Failed to submit task.')
  }
})
```

### 5. Task Failure Handling
```javascript
// Fail Button Click
failure_reason_modal.setOpen(true)

// Failure Modal Submit
fail_task.trigger().then(() => {
  if (fail_task.data.success) {
    // Same cleanup as successful submission
    current_task_container.setHidden(true)
    extraction_form.clearValue()
    
    // Refresh dashboard
    health_check.trigger()
    available_tasks.trigger()
    
    notification.showWarning('Task marked as failed.')
  }
})
```

## 📊 Real-time Updates

### Auto-refresh Logic
```javascript
// Only refresh when not actively working
const shouldRefresh = () => {
  return !current_task.data?.task?.id && 
         !submit_button.loading && 
         !get_next_task.loading
}

// Refresh timer
setInterval(() => {
  if (shouldRefresh()) {
    health_check.trigger()
    available_tasks.trigger()
  }
}, 30000) // Every 30 seconds
```

### Progress Indicators
```javascript
// Loading States
get_next_task_button.loading = get_next_task.isFetching
submit_button.loading = submit_task.isFetching
fail_button.loading = fail_task.isFetching

// Success/Error States  
notification.trigger({
  type: submit_task.data?.success ? 'success' : 'error',
  message: submit_task.data?.message || 'Operation completed'
})
```

## 🎨 Brand Consistency Checklist

✅ **Colors**: All brand colors implemented correctly  
✅ **Typography**: Inter font family used  
✅ **Gradients**: Brand gradients applied to headers/buttons  
✅ **Spacing**: Consistent 8px grid system  
✅ **Shadows**: Appropriate depth with brand-colored shadows  
✅ **Icons**: Emojis used consistently for visual hierarchy  
✅ **States**: Hover/focus states maintain brand colors  
✅ **Responsive**: Mobile-friendly layouts  

## 🔧 Customization Options

### Theme Variants
You can create additional themes by adjusting the color variables:

**Dark Mode** (optional):
- Background: `#1c2d50`
- Cards: `#2C3E50`  
- Text: `#baccd8`
- Maintain brand orange as primary

**High Contrast** (accessibility):
- Increase contrast ratios
- Maintain color relationships
- Test with accessibility tools

### Component Extensions
- Add data visualization with Chart.js using brand colors
- Create custom notification system with brand styling  
- Implement progress bars using brand gradients
- Build custom modals matching brand aesthetic

---

**Ready to build your branded Human Staging Portal in Retool!** 🚀

Use this guide as your foundation and reference the `brand_config.json` for exact color values and styling specifications. 
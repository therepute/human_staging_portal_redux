// Portal JavaScript - MINIMAL TEST VERSION

console.log('🚀 Portal.js v1.3.1 loading...');

// Global variables
let currentArticle = null;
let articleWindow = null; // Dedicated article window reference
let autoNextMode = false; // Track if we're in auto-next workflow

// API base URL for FastAPI
const API_BASE = '/api';

// Initialize portal
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Human Portal initialized');
    updateStatus('Ready');
    populateYearDropdown();
    populateDayDropdown();
});

// Populate year dropdown with current year and previous years
function populateYearDropdown() {
    const yearSelect = document.getElementById('date-year');
    if (yearSelect) {
        const currentYear = new Date().getFullYear();
        for (let year = currentYear; year >= currentYear - 10; year--) {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        }
    }
}

// Populate day dropdown
function populateDayDropdown() {
    const daySelect = document.getElementById('date-day');
    if (daySelect) {
        for (let day = 1; day <= 31; day++) {
            const option = document.createElement('option');
            option.value = day.toString().padStart(2, '0');
            option.textContent = day;
            daySelect.appendChild(option);
        }
    }
}

// Get first article and enter auto-next mode
async function getFirstArticle() {
    console.log('🎯 Getting first article and entering auto-next mode...');
    
    try {
        // Get the first article
        await getNextArticle();
        
        // Enter auto-next mode
        autoNextMode = true;
        
        // Update UI to show auto-next mode
        document.getElementById('first-article-btn').style.display = 'none';
        document.getElementById('auto-next-status').style.display = 'block';
        
        console.log('✅ Entered auto-next mode');
        
    } catch (error) {
        console.error('Error getting first article:', error);
        showMessage('❌ Failed to get first article. Please try again.', 'error');
    }
}

// Get next article
async function getNextArticle() {
    console.log('🎯 getNextArticle called!');
    
    try {
        updateStatus('Loading article...');
        
        const response = await fetch(`${API_BASE}/tasks/next?scraper_id=human_portal_user`);
        
        if (response.status === 404) {
            updateStatus('No articles available');
            showMessage('No articles available at this time.', 'info');
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.task) {
            displayArticle(data.task);
            updateStatus(`Working on: ${data.task.title.substring(0, 50)}...`);
        } else {
            throw new Error(data.message || 'No task available');
        }
        
    } catch (error) {
        console.error('Error getting article:', error);
        updateStatus('Error loading article');
        showMessage('Failed to load article. Please try again.', 'error');
    }
}

// Display article
async function displayArticle(article) {
    console.log('📄 Displaying article:', article.title);
    currentArticle = article;
    
    // Determine if we have server-provided credentials and/or if this likely needs a subscription
    const hasServerCreds = !!(article.credentials && (article.credentials.email || article.credentials.password));
    const fallbackSubscriptionHeuristic = !!(article.subscription_source && 
                            article.subscription_source.includes('_') && 
                            !article.subscription_source.startsWith('GN_'));
    
    let credentialInfo = '';
    if (hasServerCreds) {
        const cred = article.credentials;
        credentialInfo = `
            <div style="background: #fff7e6; padding: 12px; border-radius: 6px; margin: 10px 0; border-left: 4px solid #ff9800;">
                <strong>🔐 Subscription Login</strong><br>
                <small><strong>Publication:</strong> ${cred.name || (article.publication || 'Unknown')}</small><br>
                <small><strong>Domain:</strong> ${cred.domain || 'Unknown'}</small><br>
                <div style="margin-top:6px;">
                    <small><strong>Email:</strong> <code>${cred.email || '—'}</code></small>
                    <button class="btn btn-secondary copy-btn" data-value="${(cred.email || '').replace(/"/g, '&quot;')}">Copy Email</button>
                </div>
                <div style="margin-top:6px;">
                    <small><strong>Password:</strong> <code>${cred.password || '—'}</code></small>
                    <button class="btn btn-secondary copy-btn" data-value="${(cred.password || '').replace(/"/g, '&quot;')}">Copy Password</button>
                </div>
                ${cred.notes ? `<div style="margin-top:6px;"><small><strong>Notes:</strong> ${cred.notes}</small></div>` : ''}
            </div>
        `;
    } else if (fallbackSubscriptionHeuristic) {
        credentialInfo = `
            <div style="background: #e8f4fd; padding: 12px; border-radius: 6px; margin: 10px 0; border-left: 4px solid #2196F3;">
                <strong>🔐 Subscription Required:</strong><br>
                <small>Check password manager for credentials to: <strong>${article.subscription_source}</strong></small>
            </div>
        `;
    }
    
    const articleContent = document.getElementById('article-content');

    // Build Priority label from focus_industry or clients
    let priorityLine = '';
    const hasFocus = Array.isArray(article.focus_industry)
        ? article.focus_industry.length > 0
        : (article.focus_industry && String(article.focus_industry).trim() !== '');
    const hasClient = Array.isArray(article.clients)
        ? article.clients.length > 0
        : (article.clients && String(article.clients).trim() !== '');

    if (hasFocus) {
        const value = Array.isArray(article.focus_industry) ? article.focus_industry.join(', ') : article.focus_industry;
        priorityLine = `<p><strong>Priority:</strong> Focus Industry - ${value}</p>`;
    } else if (hasClient) {
        const value = Array.isArray(article.clients) ? article.clients.join(', ') : article.clients;
        priorityLine = `<p><strong>Priority:</strong> Client - ${value}</p>`;
    }

    // Domain helpers
    const getDomainFromUrl = (url) => {
        try { const u = new URL(url); return u.hostname.replace(/^www\./, '').toLowerCase(); } catch { return ''; }
    };
    const articleDomain = getDomainFromUrl(article.permalink_url);
    const isForbes = articleDomain.endsWith('forbes.com');

    // URL section
    let urlSection = '';
    if (isForbes) {
        const cred = article.credentials || {};
        const email = cred.email || '';
        const password = cred.password || '';
        urlSection = `
            <div class="article-url-section" style="margin-top: 10px;">
                <p><strong>Manual Login Required (Forbes)</strong></p>
                <div style="background:#fff7e6;padding:12px;border-radius:6px;border-left:4px solid #ff9800;">
                    <div style="margin-bottom:8px;">
                        1) Open a NEW browser tab, go to <strong>forbes.com</strong>, and sign in first.
                    </div>
                    <div style="margin-bottom:8px;">
                        2) After login, open this article URL:
                        <div style="display:flex;gap:8px;align-items:center;margin-top:6px;">
                            <small style="color:#666; font-style: italic;">${article.permalink_url}</small>
                            <button class="btn btn-secondary copy-btn" data-value="${article.permalink_url.replace(/"/g, '&quot;')}">Copy Link</button>
                        </div>
                    </div>
                    ${(email || password) ? `
                    <div>
                        <div><small><strong>Email:</strong> <code>${email || '—'}</code> <button class="btn btn-secondary copy-btn" data-value="${(email || '').replace(/"/g, '&quot;')}">Copy</button></small></div>
                        <div><small><strong>Password:</strong> <code>${password || '—'}</code> <button class="btn btn-secondary copy-btn" data-value="${(password || '').replace(/"/g, '&quot;')}">Copy</button></small></div>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    } else {
        urlSection = `
            <div class="article-url-section">
                <p><strong>Article URL:</strong></p>
                <button class="btn btn-primary" onclick="openArticleWindow('${article.permalink_url}')" style="margin: 10px 0;">
                    📖 Open Article in Dedicated Window
                </button>
                <div style="display:flex;gap:8px;align-items:center;margin-top:6px;">
                    <small style="color: #666; font-style: italic;">${article.permalink_url}</small>
                    <button class="btn btn-secondary copy-btn" data-value="${article.permalink_url.replace(/"/g, '&quot;')}">Copy Link</button>
                </div>
            </div>
        `;
    }

    articleContent.innerHTML = `
        <div class="article-title">${article.title}</div>
        <div class="article-text">
            <p><strong>Publication:</strong> ${article.publication || 'Empty - need from scraper'}</p>
            <p><strong>Published Date:</strong> ${article.published_at ? formatDate(article.published_at) : '❌ Missing - need from scraper'}</p>
            <p><strong>Author:</strong> ${article.actor_name || '❌ Missing - need from scraper'}</p>
            ${priorityLine}
            ${credentialInfo}
            <hr>
            ${urlSection}
            <div class="data-status">
                <strong>Data Status:</strong><br>
                ✅ <strong>Have:</strong> Headline, Story_Link, Priority<br>
                ❌ <strong>Need:</strong> ${getMissingFields(article).join(', ')}, Body (always)
            </div>
        </div>
    `;
    
    document.getElementById('current-article-id').textContent = article.id;
    document.getElementById('unable-btn').disabled = false;
    document.getElementById('submit-btn').disabled = false;
    
    // Load smart field detection based on actual missing data
    await loadRequiredFields(article);
}

// Determine what fields are actually missing
function getMissingFields(article) {
    const missing = [];

    function isPublicationMissing(pub) {
        if (!pub) return true;
        const val = String(pub).trim().toLowerCase();
        if (!val) return true;
        // Treat placeholder values as missing
        return val === 'unknown publication' || val === 'unknown' || val === 'n/a';
    }
    
    if (!article.published_at) {
        missing.push('Date');
    }
    
    if (!article.actor_name) {
        missing.push('Author');
    }
    
    // Publication considered missing if empty or placeholder (Unknown/N/A)
    if (isPublicationMissing(article.publication)) {
        missing.push('Publication');
    }
    
    return missing;
}

// Smart field detection - only show needed fields
async function loadRequiredFields(article) {
    try {
        console.log('🧠 Analyzing existing data for:', article.id);
        
        // Show loading state
        document.getElementById('loading-fields').style.display = 'block';
        document.getElementById('dynamic-fields').style.display = 'none';
        
        // Determine what's missing based on actual data
        const missingFields = getMissingFields(article);
        console.log('🧠 Missing fields:', missingFields);
        
        // Hide loading, show form
        document.getElementById('loading-fields').style.display = 'none';
        document.getElementById('dynamic-fields').style.display = 'block';
        
        // Show/hide fields based on what's actually missing
        const dateGroup = document.getElementById('date-group');
        const authorGroup = document.getElementById('author-group'); 
        const headlineGroup = document.getElementById('headline-group');
        const publicationGroup = document.getElementById('publication-group');
        
        // Date field - show if published_at is null
        if (!article.published_at) {
            dateGroup.style.display = 'block';
            console.log('📅 Date field required - published_at is null');
        } else {
            dateGroup.style.display = 'none';
            console.log('📅 Date field NOT needed - have published_at:', article.published_at);
        }
        
        // Author field - show if source_title/actor_name missing
        if (!article.actor_name) {
            authorGroup.style.display = 'block';
            console.log('👤 Author field required - actor_name is null');
        } else {
            authorGroup.style.display = 'none';
            console.log('👤 Author field NOT needed - have:', article.actor_name);
        }
        
        // Headline field - show if title missing (unlikely)
        if (!article.title) {
            headlineGroup.style.display = 'block';
            console.log('📰 Headline field required - title is missing');
        } else {
            headlineGroup.style.display = 'none';
            console.log('📰 Headline field NOT needed - have title:', article.title.substring(0, 50) + '...');
        }
        
        // Publication field - show if empty or placeholder (Unknown/N/A)
        const isPubMissing = (() => {
            if (!article.publication) return true;
            const val = String(article.publication).trim().toLowerCase();
            return !val || val === 'unknown publication' || val === 'unknown' || val === 'n/a';
        })();

        if (isPubMissing) {
            if (publicationGroup) {
                publicationGroup.style.display = 'block';
                console.log('🏢 Publication field required - publication is empty/unknown');
            }
        } else {
            if (publicationGroup) {
                publicationGroup.style.display = 'none';
                console.log('🏢 Publication field NOT needed - have:', article.publication);
            }
        }
        
        // Body is ALWAYS required from scraper
        console.log('📝 Body field always required from scraper');
        
        // Update submit button text with actual count
        const requiredFields = missingFields.length + 1; // +1 for body
        document.getElementById('submit-btn').textContent = `Submit Extraction (${requiredFields} fields needed)`;
        
    } catch (error) {
        console.error('Error analyzing field requirements:', error);
        showMessage('⚠️ Error analyzing fields - showing all', 'warning');
    }
}

// Open article in dedicated window
function openArticleWindow(url) {
    console.log('🔗 Opening article window:', url);
    
    if (!url) {
        showMessage('No article URL available.', 'error');
        return;
    }
    
    // Open or reuse the dedicated article window
    if (!articleWindow || articleWindow.closed) {
        // First time opening or window was closed
        articleWindow = window.open(
            url,
            'article_extraction_window',
            'width=1200,height=900,scrollbars=yes,resizable=yes,toolbar=yes,location=yes'
        );
        
        if (articleWindow) {
            showMessage('📖 Article window opened - keep both windows open!', 'success');
            articleWindow.focus();
        } else {
            showMessage('❌ Popup blocked! Please allow popups.', 'error');
            return;
        }
    } else {
        // Window exists, just load new URL
        articleWindow.location.href = url;
        articleWindow.focus();
        console.log('🔄 Loaded new article in existing window');
    }
}

// Submit extraction
async function submitExtraction() {
    console.log('📤 Submit called!');
    
    if (!currentArticle) {
        showMessage('No article loaded.', 'error');
        return;
    }
    
    // Get body content (always required)
    const bodyContent = document.getElementById('body-field').value.trim();
    if (!bodyContent) {
        showMessage('Please provide article body text.', 'error');
        document.getElementById('body-field').focus();
        return;
    }
    
    // Start with data from soup_dedupe, override with scraper data where provided
    const extractionData = {
        task_id: currentArticle.id,
        scraper_id: 'human_portal_user',
        
        // These come from soup_dedupe (carry over as-is)
        story_link: currentArticle.permalink_url,
        search: currentArticle.subscription_source,
        source: currentArticle.source,
        client_priority: currentArticle.client_priority,
        pub_tier: currentArticle.pub_tier, // Add pub_tier field
        
        // Body always from scraper
        body: bodyContent,
        
        // These use soup_dedupe data OR scraper data (scraper overrides)
        headline: currentArticle.title, // Use existing unless scraper provides
        publication: currentArticle.publication, // Use existing unless scraper provides
        date: currentArticle.published_at ? currentArticle.published_at.split('T')[0] : null, // Use existing unless scraper provides
        author: currentArticle.actor_name || currentArticle.source_title, // Prefer actor_name from soup_dedupe
        
        duration_sec: null // Will add timer later
    };
    
    // Override with scraper data if provided
    const dateYear = document.getElementById('date-year');
    const dateMonth = document.getElementById('date-month');
    const dateDay = document.getElementById('date-day');
    const dateNotAvailable = document.getElementById('date-group').hasAttribute('data-not-available');
    
    if (dateNotAvailable) {
        extractionData.date = 'Not Available';
        console.log('📅 Using "Not Available" for date');
    } else if (dateYear && dateMonth && dateDay && 
        dateYear.offsetParent !== null && 
        dateYear.value && dateMonth.value && dateDay.value) {
        extractionData.date = `${dateYear.value}-${dateMonth.value}-${dateDay.value}`;
        console.log('📅 Using scraper date:', extractionData.date);
    } else if (extractionData.date) {
        console.log('📅 Using existing date:', extractionData.date);
    }
    
    const authorField = document.getElementById('author-field');
    if (authorField && authorField.offsetParent !== null) {
        if (authorField.disabled && authorField.value === 'Not Available') {
            extractionData.author = 'Not Available';
            console.log('👤 Using "Not Available" for author');
        } else if (authorField.value.trim()) {
            extractionData.author = authorField.value.trim();
            console.log('👤 Using scraper author:', authorField.value);
        }
    } else if (extractionData.author) {
        console.log('👤 Using existing author:', extractionData.author);
    }
    
    const publicationField = document.getElementById('publication-field');
    if (publicationField && publicationField.offsetParent !== null) {
        if (publicationField.disabled && publicationField.value === 'Not Available') {
            extractionData.publication = 'Not Available';
            console.log('🏢 Using "Not Available" for publication');
        } else if (publicationField.value.trim()) {
            extractionData.publication = publicationField.value.trim();
            console.log('🏢 Using scraper publication:', publicationField.value);
        }
    } else if (extractionData.publication) {
        console.log('🏢 Using existing publication:', extractionData.publication);
    }
    
    const headlineField = document.getElementById('headline-field');
    if (headlineField && headlineField.offsetParent !== null && headlineField.value.trim()) {
        extractionData.headline = headlineField.value.trim();
        console.log('📰 Using scraper headline:', headlineField.value);
    } else {
        console.log('📰 Using existing headline:', extractionData.headline);
    }
    
    console.log('📤 Final extraction data for the_soups:', extractionData);
    
    // Debug: Log each field to see what's being sent
    console.log('🔍 SUBMISSION DEBUG:');
    console.log('  - Body (required):', extractionData.body ? '✅ PROVIDED' : '❌ MISSING');
    console.log('  - Publication:', extractionData.publication || 'Using soup_dedupe data');
    console.log('  - Author:', extractionData.author || 'Using soup_dedupe data');
    console.log('  - Date:', extractionData.date || 'Using soup_dedupe data');
    console.log('  - Headline:', extractionData.headline || 'Using soup_dedupe data');
    console.log('  - Story Link:', extractionData.story_link);
    console.log('  - Task ID:', extractionData.task_id);
    console.log('📋 FULL PAYLOAD:', JSON.stringify(extractionData, null, 2));
    
    try {
        updateStatus('Submitting to the_soups...');
        
        console.log('🌐 Making API call to:', `${API_BASE}/tasks/submit`);
        
        const response = await fetch(`${API_BASE}/tasks/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(extractionData)
        });
        
        console.log('📡 API Response status:', response.status);
        console.log('📡 API Response headers:', [...response.headers.entries()]);
        
        // Get response text first to debug
        const responseText = await response.text();
        console.log('📡 Raw response text:', responseText);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${responseText}`);
        }
        
        // Try to parse as JSON
        let result;
        try {
            result = JSON.parse(responseText);
        } catch (parseError) {
            console.error('❌ Failed to parse response as JSON:', parseError);
            throw new Error(`Invalid JSON response: ${responseText}`);
        }
        
        console.log('📡 Parsed result:', result);
        
        if (result.success) {
            showMessage('✅ Extraction submitted to the_soups successfully!', 'success');
            
            if (autoNextMode) {
                // Auto-next mode: clear form and immediately load next, then auto-open window
                clearForm();
                console.log('🔄 Auto-next mode: Loading next article...');
                updateStatus('Auto-loading next article...');

                currentArticle = null;

                setTimeout(async () => {
                    try {
                        await getNextArticle();
                        console.log('✅ Auto-next: Successfully loaded next article');
                        // Auto-open dedicated article window for the newly loaded article
                        if (currentArticle && currentArticle.permalink_url) {
                            openArticleWindow(currentArticle.permalink_url);
                        }
                    } catch (error) {
                        console.error('❌ Auto-next failed:', error);
                        showMessage('Auto-next failed. Click "Get Next Article" manually.', 'warning');
                        autoNextMode = false;
                        document.getElementById('first-article-btn').style.display = 'block';
                        document.getElementById('auto-next-status').style.display = 'none';
                    }
                }, 500);
            } else {
                // Manual mode: just clear and wait
                clearForm();
                currentArticle = null;
                updateStatus('Ready for next article');
            }
        } else {
            throw new Error(result.message || 'Submission failed');
        }
        
    } catch (error) {
        console.error('Error submitting extraction:', error);
        console.error('Full error details:', {
            message: error.message,
            stack: error.stack,
            extractionData: extractionData
        });
        showMessage('❌ Failed to submit extraction. Check console for details.', 'error');
        updateStatus('Submission failed');
    }
}

// Unable to Extract modal functions
function showUnableToExtractModal() {
    if (!currentArticle) {
        showMessage('No article loaded.', 'error');
        return;
    }
    
    document.getElementById('unable-modal').style.display = 'flex';
    document.getElementById('unable-reason').value = '';
    document.getElementById('unable-explanation').style.display = 'none';
    document.getElementById('unable-explanation').value = '';
    
    // Add quick preset for subscription/login issues
    const reasonSelect = document.getElementById('unable-reason');
    if (reasonSelect && !Array.from(reasonSelect.options).some(o => o.value === 'login_subscription')) {
        const opt = document.createElement('option');
        opt.value = 'login_subscription';
        opt.text = 'Login/Subscription Not Working';
        reasonSelect.add(opt, reasonSelect.options[1] || null);
    }
}

function closeUnableModal() {
    document.getElementById('unable-modal').style.display = 'none';
    
    // Clear modal form data
    document.getElementById('unable-reason').value = '';
    document.getElementById('unable-explanation').style.display = 'none';
    document.getElementById('unable-explanation').value = '';
    
    console.log('🚫 Unable modal closed and cleared');
}

// Show explanation field when "Other" is selected
document.addEventListener('DOMContentLoaded', function() {
    const reasonSelect = document.getElementById('unable-reason');
    const explanationField = document.getElementById('unable-explanation');
    
    if (reasonSelect && explanationField) {
        reasonSelect.addEventListener('change', function() {
            if (this.value === 'other') {
                explanationField.style.display = 'block';
                explanationField.required = true;
            } else {
                explanationField.style.display = 'none';
                explanationField.required = false;
                explanationField.value = '';
            }
        });
    }
});

async function confirmUnable() {
    const reason = document.getElementById('unable-reason').value;
    const explanation = document.getElementById('unable-explanation').value.trim();
    
    if (!reason) {
        showMessage('Please select a reason.', 'error');
        return;
    }
    
    if (reason === 'other' && !explanation) {
        showMessage('Please explain the issue.', 'error');
        document.getElementById('unable-explanation').focus();
        return;
    }
    
    try {
        updateStatus('Marking as unable to extract...');
        
        const reasonMap = {
            paywall_no_subscription: 'Cannot Access - Paywall with no subscription',
            subscription_not_working: 'Cannot Access - Subscription provided but not working',
            no_article: 'Cannot Access - No article available/does not open',
            not_english: 'Not English Language',
            video_content: 'Video content'
        };
        const friendly = reason === 'other' ? `Other: ${explanation}` : (reasonMap[reason] || reason.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()));
        
        // Capture the full reason for the database
        let fullReason;
        if (reason === 'other') {
            fullReason = `Unable to extract - Other: ${explanation}`;
        } else {
            fullReason = `Unable to extract - ${friendly}`;
        }
        
        console.log('🚫 Attempting to mark as unable:', {
            task_id: currentArticle.id,
            scraper_id: 'human_portal_user',
            error_message: fullReason
        });
        
        const response = await fetch(`${API_BASE}/tasks/fail`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                task_id: currentArticle.id,
                scraper_id: 'human_portal_user',
                error_message: fullReason
            })
        });
        
        console.log('🚫 Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('🚫 Response error:', errorText);
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`🚫 Marked as unable to extract: ${friendly}`, 'info');
            
            // IMMEDIATELY close modal and clear current article
            closeUnableModal();
            currentArticle = null;
            updateStatus('Auto-loading next article...');
            
            if (autoNextMode) {
                // Auto-next mode: immediately load next article
                console.log('🔄 Auto-next mode: Loading next article after unable...');
                
                setTimeout(async () => {
                    try {
                        await getNextArticle();
                        console.log('✅ Auto-next: Successfully loaded next article after unable');
                    } catch (error) {
                        console.error('❌ Auto-next failed after unable:', error);
                        showMessage('Auto-next failed. Click "Get First Article" to restart.', 'warning');
                        autoNextMode = false;
                        clearForm();
                    }
                }, 500); // Shorter delay for immediate response
            } else {
                // Manual mode
                clearForm();
                updateStatus('Ready for next article');
            }
        } else {
            throw new Error(result.message || 'Failed to mark as unable');
        }
        
    } catch (error) {
        console.error('Error marking as unable:', error);
        console.error('Full error details:', {
            message: error.message,
            stack: error.stack,
            currentArticle: currentArticle ? currentArticle.id : 'none'
        });
        showMessage('❌ Failed to mark as unable. Check console for details.', 'error');
        updateStatus('Error marking as unable');
    }
}

// Mark field as "Not Available"
function markFieldNotAvailable(fieldType) {
    console.log(`🚫 Marking ${fieldType} as not available`);
    
    switch(fieldType) {
        case 'publication':
            document.getElementById('publication-field').value = 'Not Available';
            document.getElementById('publication-field').disabled = true;
            break;
        case 'author':
            document.getElementById('author-field').value = 'Not Available';
            document.getElementById('author-field').disabled = true;
            break;
        case 'date':
            document.getElementById('date-year').value = '';
            document.getElementById('date-month').value = '';
            document.getElementById('date-day').value = '';
            document.getElementById('date-year').disabled = true;
            document.getElementById('date-month').disabled = true;
            document.getElementById('date-day').disabled = true;
            // Set a flag to indicate date is not available
            document.getElementById('date-group').setAttribute('data-not-available', 'true');
            break;
    }
    
    showMessage(`✅ ${fieldType.charAt(0).toUpperCase() + fieldType.slice(1)} marked as "Not Available"`, 'info');
}

// Clear form
function clearForm() {
    console.log('🧹 Clear form called!');
    
    // Clear all input fields and reset disabled states
    const publicationField = document.getElementById('publication-field');
    publicationField.value = '';
    publicationField.disabled = false;
    
    const authorField = document.getElementById('author-field');
    authorField.value = '';
    authorField.disabled = false;
    
    document.getElementById('date-year').value = '';
    document.getElementById('date-month').value = '';
    document.getElementById('date-day').value = '';
    document.getElementById('date-year').disabled = false;
    document.getElementById('date-month').disabled = false;
    document.getElementById('date-day').disabled = false;
    document.getElementById('date-group').removeAttribute('data-not-available');
    
    document.getElementById('headline-field').value = '';
    document.getElementById('body-field').value = '';
    document.getElementById('extraction-notes').value = '';
    
    if (!autoNextMode) {
        // Only reset to initial state if not in auto-next mode
        document.getElementById('loading-fields').style.display = 'block';
        document.getElementById('dynamic-fields').style.display = 'none';
        
        // Reset article display
        const articleContent = document.getElementById('article-content');
        articleContent.innerHTML = '<div class="no-article"><p>Click "Get First Article" to start extraction workflow.</p></div>';
        
        // Reset UI state
        document.getElementById('current-article-id').textContent = 'None';
        document.getElementById('unable-btn').disabled = true;
        document.getElementById('submit-btn').disabled = true;
        document.getElementById('submit-btn').textContent = 'Submit Extraction';
        
        // Show first article button
        document.getElementById('first-article-btn').style.display = 'block';
        document.getElementById('auto-next-status').style.display = 'none';
    }
    
    showMessage('🧹 Form cleared!', 'info');
}

// Utility functions
function updateStatus(status) {
    console.log('📊 Status:', status);
    const element = document.getElementById('current-status');
    if (element) {
        element.textContent = status;
    }
}

function showMessage(text, type = 'info') {
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    console.log(`${icon} ${text}`);
    alert(`${icon} ${text}`);
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    try {
        return new Date(dateString).toLocaleDateString();
    } catch {
        return 'Unknown';
    }
}

async function copyToClipboard(text) {
    // Decode common HTML entities that may be present in data-value
    const decoded = String(text)
        .replace(/&quot;/g, '"')
        .replace(/&amp;/g, '&')
        .replace(/&#39;/g, "'");
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(decoded);
            showMessage('Copied to clipboard', 'info');
            return;
        }
    } catch (e) {
        // Fallback below
    }
    // Fallback: temporary textarea + execCommand
    const ta = document.createElement('textarea');
    ta.value = decoded;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand('copy');
        showMessage('Copied to clipboard', 'info');
    } catch (e) {
        showMessage('Copy failed', 'error');
    } finally {
        document.body.removeChild(ta);
    }
}

// Delegate copy buttons
document.addEventListener('click', function(e) {
    const target = e.target;
    if (target && target.classList && target.classList.contains('copy-btn')) {
        const value = target.getAttribute('data-value') || '';
        if (value) {
            copyToClipboard(value);
        } else {
            showMessage('Nothing to copy', 'warning');
        }
    }
});

console.log('✅ Portal.js loaded successfully!');
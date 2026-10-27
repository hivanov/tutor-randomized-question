/**
 * Rich Text & Math Renderer for Randomized Question XBlock
 */
var RichTextRenderer = (function() {
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    var mathEngineLoading = false;
    var pendingContainers = [];

    function ensureMathEngine(callback) {
        if (window.renderMathInElement || (window.katex && window.katex.renderToString) || window.MathJax) {
            if (callback) callback();
            return;
        }

        if (callback) pendingContainers.push(callback);
        if (mathEngineLoading) return;
        mathEngineLoading = true;

        if (!document.getElementById('rq-katex-css')) {
            var link = document.createElement('link');
            link.id = 'rq-katex-css';
            link.rel = 'stylesheet';
            link.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css';
            document.head.appendChild(link);
        }

        function loadAutoRender() {
            if (!document.getElementById('rq-katex-autorender-js')) {
                var autoScript = document.createElement('script');
                autoScript.id = 'rq-katex-autorender-js';
                autoScript.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js';
                autoScript.onload = function() {
                    flushPending();
                };
                document.head.appendChild(autoScript);
            } else {
                flushPending();
            }
        }

        function flushPending() {
            var cbs = pendingContainers.slice();
            pendingContainers = [];
            cbs.forEach(function(fn) {
                try { fn(); } catch(e) {}
            });
        }

        if (!document.getElementById('rq-katex-js')) {
            var script = document.createElement('script');
            script.id = 'rq-katex-js';
            script.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js';
            script.onload = loadAutoRender;
            document.head.appendChild(script);
        } else {
            loadAutoRender();
        }
    }

    function highlightSyntax(code, lang) {
        if (window.hljs && lang && window.hljs.getLanguage(lang)) {
            try {
                return window.hljs.highlight(code, { language: lang }).value;
            } catch (e) {
                // fallback to default escaping
            }
        }
        
        var esc = escapeHtml(code);
        esc = esc.replace(/(#[^\n]*|\/\/[^\n]*)/g, '<span class="tok-comment">$1</span>');
        esc = esc.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g, '<span class="tok-string">$1</span>');
        esc = esc.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tok-number">$1</span>');
        var keywords = /\b(def|class|return|if|else|elif|for|while|import|from|in|is|not|and|or|None|True|False|self|async|await|const|let|var|function|SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN)\b/g;
        esc = esc.replace(keywords, '<span class="tok-keyword">$1</span>');
        return esc;
    }

    function parseMarkdown(text) {
        if (!text) return '';
        var codeBlocks = [];
        var inlineCodes = [];
        var mathBlocks = [];
        var mathInlines = [];

        // 1. Code blocks
        var processed = text.replace(/```([a-zA-Z0-9_\-]+)?\n([\s\S]*?)```/g, function(match, lang, code) {
            var placeholder = '§§§CODEBLOCK' + codeBlocks.length + '§§§';
            var highlighted = highlightSyntax(code.trim(), (lang || '').toLowerCase());
            codeBlocks.push(
                '<pre class="code-block' + (lang ? ' language-' + lang : '') + '">' +
                '<code class="code-inner' + (lang ? ' language-' + lang : '') + '">' +
                highlighted +
                '</code></pre>'
            );
            return placeholder;
        });

        // 2. Inline code
        processed = processed.replace(/`([^`\n]+)`/g, function(match, code) {
            var placeholder = '§§§INLINECODE' + inlineCodes.length + '§§§';
            inlineCodes.push('<code class="inline-code">' + escapeHtml(code) + '</code>');
            return placeholder;
        });

        // 3. Block math $$...$$ or \[...\]
        processed = processed.replace(/\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]/g, function(match, m1, m2) {
            var math = (m1 !== undefined ? m1 : m2).trim();
            var placeholder = '§§§MATHBLOCK' + mathBlocks.length + '§§§';
            mathBlocks.push('$$\n' + math + '\n$$');
            return placeholder;
        });

        // 4. Inline math $...$ or \(...\)
        processed = processed.replace(/(^|[^\\])\$([^\$\n]+?)\$|\\\(([\s\S]*?)\\\)/g, function(match, prefix, m1, m2) {
            var math = (m1 !== undefined ? m1 : m2).trim();
            var leading = (m1 !== undefined && prefix) ? prefix : '';
            var placeholder = '§§§MATHINLINE' + mathInlines.length + '§§§';
            mathInlines.push('$' + math + '$');
            return leading + placeholder;
        });

        // 5. Bold & Italic formatting
        processed = processed
            .replace(/\*\*\*([^*\n]+)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
            .replace(/__([^_\n]+)__/g, '<strong>$1</strong>')
            .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
            .replace(/\b_([^_\n]+)_\b/g, '<em>$1</em>');

        // 6. Line breaks
        processed = processed.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');

        // 7. Restore tokens in reverse order
        mathInlines.forEach(function(math, i) {
            processed = processed.replace('§§§MATHINLINE' + i + '§§§', math);
        });
        mathBlocks.forEach(function(math, i) {
            processed = processed.replace('§§§MATHBLOCK' + i + '§§§', math);
        });
        inlineCodes.forEach(function(codeHtml, i) {
            processed = processed.replace('§§§INLINECODE' + i + '§§§', codeHtml);
        });
        codeBlocks.forEach(function(blockHtml, i) {
            processed = processed.replace('§§§CODEBLOCK' + i + '§§§', blockHtml);
        });

        return processed;
    }

    function typeset(container) {
        if (!container) return;

        // 1. KaTeX renderMathInElement
        if (window.renderMathInElement) {
            try {
                window.renderMathInElement(container, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
                        { left: '\\[', right: '\\]', display: true },
                        { left: '$', right: '$', display: false },
                        { left: '\\(', right: '\\)', display: false }
                    ],
                    throwOnError: false
                });
                return;
            } catch (e) {
                // fall through
            }
        }

        // 2. Open edX MathJax typesetting
        if (window.MathJax) {
            try {
                if (window.MathJax.typesetPromise) {
                    window.MathJax.typesetPromise([container]).catch(function(e) { /* ignore */ });
                    return;
                } else if (window.MathJax.Hub && window.MathJax.Hub.Queue) {
                    window.MathJax.Hub.Queue(['Typeset', window.MathJax.Hub, container]);
                    return;
                }
            } catch (err) {
                // fall through
            }
        }

        // 3. Fallback: ensure math engine loads and typeset
        ensureMathEngine(function() {
            typeset(container);
        });
    }

    function render(container, rawText) {
        if (!container) return;
        if (!rawText) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = parseMarkdown(rawText);
        typeset(container);
    }

    return {
        render: render,
        parseMarkdown: parseMarkdown,
        typeset: typeset,
        escapeHtml: escapeHtml
    };
})();

function RandomizedQuestionStudentView(runtime, element, initData) {
    var $el = $(element);
    var data = initData || {};

    var submitUrl = runtime.handlerUrl(element, 'submit_answer');
    var resetUrl = runtime.handlerUrl(element, 'reset_problem');

    function renderView() {
        $el.find('.problem-title').text(data.display_name || 'Question');
        RichTextRenderer.render($el.find('.problem-prompt')[0], data.prompt || '');
        
        var isSingle = data.is_single_choice || false;
        $el.find('.instruction-text').text(
            isSingle ? 'Choose the single best answer.' : 'Select all options that apply.'
        );

        $el.find('.attempts-badge').text('Attempts: ' + (data.attempts || 0) + ' / ' + (data.max_attempts || 3));
        $el.find('.points-badge').text('Weight: ' + (data.weight || 1.0) + ' pt' + (data.weight === 1.0 ? '' : 's'));

        var $optionsContainer = $el.find('.options-container');
        $optionsContainer.empty();

        var inputType = isSingle ? 'radio' : 'checkbox';
        var selectedSet = new Set(data.selected_ids || []);
        var isCompleted = !!data.completed;
        var showCorrectness = data.show_correctness === 'always' || (data.show_correctness === 'past_due' && data.past_due);

        (data.options || []).forEach(function(opt) {
            var isChecked = selectedSet.has(opt.id);
            var $item = $('<div class="option-item"></div>');
            if (isChecked) {
                $item.addClass('selected');
            }

            var $input = $('<input class="option-input">')
                .attr('type', inputType)
                .attr('name', 'option_' + runtime.elementId)
                .attr('value', opt.id)
                .prop('checked', isChecked);

            if (isCompleted) {
                $input.prop('disabled', true);
            }

            var $contentWrapper = $('<div class="option-content-wrapper"></div>');
            var $label = $('<label class="option-label"></label>');
            var $labelText = $('<span class="option-text-span"></span>');
            RichTextRenderer.render($labelText[0], opt.text);
            $label.append($labelText);

            // Correctness badge if revealed
            if (isCompleted && showCorrectness && opt.is_correct !== null && opt.is_correct !== undefined) {
                if (opt.is_correct) {
                    $item.addClass('is-correct');
                    $label.append(' <span class="option-badge option-badge-correct">&#10003; Correct Answer</span>');
                } else {
                    $item.addClass('is-incorrect');
                    $label.append(' <span class="option-badge option-badge-incorrect">&#10007; Incorrect Option</span>');
                }
            }

            $contentWrapper.append($label);

            // Option-level explanation if revealed
            if (isCompleted && showCorrectness && opt.explanation && opt.explanation.trim()) {
                var $explBox = $('<div class="option-explanation-box"></div>');
                var $explTag = $('<span class="option-expl-tag"><span class="expl-icon">&#128161;</span> Explanation:</span>');
                var $explBody = $('<div class="option-expl-body"></div>');
                RichTextRenderer.render($explBody[0], opt.explanation);
                $explBox.append($explTag).append($explBody);
                $contentWrapper.append($explBox);
            }

            $item.append($input).append($contentWrapper);

            $item.on('click', function(e) {
                if ($input.prop('disabled') || isCompleted) return;
                if (!$(e.target).is('input') && !$(e.target).closest('.option-explanation-box').length) {
                    if (isSingle) {
                        $input.prop('checked', true).trigger('change');
                    } else {
                        $input.prop('checked', !$input.prop('checked')).trigger('change');
                    }
                }
            });

            $input.on('change', function() {
                if (isSingle) {
                    $optionsContainer.find('.option-item').removeClass('selected');
                    if ($input.prop('checked')) {
                        $item.addClass('selected');
                    }
                } else {
                    $item.toggleClass('selected', $input.prop('checked'));
                }
            });

            $optionsContainer.append($item);
        });

        // Submit / Reset buttons
        var $btnSubmit = $el.find('.btn-submit');
        var $btnReset = $el.find('.btn-reset');

        if (data.completed) {
            $btnSubmit.prop('disabled', true);
            if (data.raw_score_fraction >= 1.0) {
                $btnSubmit.text('Submitted (100% Correct)');
                $btnReset.hide();
            } else if (data.attempts < data.max_attempts) {
                $btnSubmit.text('Submitted');
                $btnReset.show().prop('disabled', false).text('Try New Attempt');
            } else {
                $btnSubmit.text('Final Attempt Submitted');
                $btnReset.hide();
            }
        } else {
            if (data.attempts >= data.max_attempts) {
                $btnSubmit.prop('disabled', true).text('No Attempts Remaining');
                $btnReset.hide();
            } else {
                $btnSubmit.prop('disabled', false).text('Submit Answer');
                $btnReset.hide();
            }
        }

        // Show feedback if already completed
        if (data.completed) {
            showFeedback({
                score: data.score,
                max_score: data.weight,
                is_correct: data.raw_score_fraction >= 1.0,
                feedback: data.last_feedback,
                explanation: data.explanation
            });
        }
    }

    function showFeedback(result) {
        var $fbContainer = $el.find('.feedback-container');
        var $fbAlert = $fbContainer.find('.feedback-alert');
        $fbAlert.removeClass('alert-success alert-warning alert-danger');

        var isCorrect = result.is_correct || result.score >= result.max_score;
        var isPartial = result.score > 0 && result.score < result.max_score;

        if (isCorrect) {
            $fbAlert.addClass('alert-success');
            $fbAlert.find('.feedback-title').text('Correct (' + result.score + ' / ' + result.max_score + ' pts)');
        } else if (isPartial) {
            $fbAlert.addClass('alert-warning');
            $fbAlert.find('.feedback-title').text('Partially Correct (' + result.score + ' / ' + result.max_score + ' pts)');
        } else {
            $fbAlert.addClass('alert-danger');
            $fbAlert.find('.feedback-title').text('Incorrect (0 / ' + result.max_score + ' pts)');
        }

        RichTextRenderer.render($fbAlert.find('.feedback-message')[0], result.feedback || '');
        $fbContainer.slideDown(200);

        if (result.explanation) {
            RichTextRenderer.render($el.find('.explanation-content')[0], result.explanation);
            $el.find('.explanation-container').slideDown(200);
        }
    }

    $el.find('.btn-submit').on('click', function() {
        var selected = [];
        $el.find('.option-input:checked').each(function() {
            selected.push($(this).val());
        });

        if (selected.length === 0) {
            alert('Please select at least one option before submitting.');
            return;
        }

        var $btn = $(this);
        $btn.prop('disabled', true).text('Evaluating...');

        $.ajax({
            type: 'POST',
            url: submitUrl,
            data: JSON.stringify({ selected_ids: selected }),
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(resp) {
                $btn.prop('disabled', false).text('Submit Answer');
                if (resp.success) {
                    data.attempts = resp.attempts;
                    data.completed = true;
                    data.last_feedback = resp.feedback;
                    data.score = resp.score;
                    data.raw_score_fraction = resp.raw_score_fraction;
                    data.selected_ids = selected;
                    data.explanation = resp.explanation;
                    if (resp.options && resp.options.length > 0) {
                        data.options = resp.options;
                    }

                    renderView();
                    showFeedback(resp);
                } else {
                    alert('Submission error: ' + (resp.error || 'Unknown error'));
                }
            },
            error: function(err) {
                $btn.prop('disabled', false).text('Submit Answer');
                alert('An error occurred during submission.');
            }
        });
    });

    $el.find('.btn-reset').on('click', function() {
        var $btn = $(this);
        $btn.prop('disabled', true).text('Reseeding...');

        $.ajax({
            type: 'POST',
            url: resetUrl,
            data: JSON.stringify({}),
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(resp) {
                $btn.prop('disabled', false).text('Try New Attempt');
                if (resp.success) {
                    data.options = resp.options;
                    data.selected_ids = [];
                    data.completed = false;
                    $el.find('.feedback-container').slideUp(150);
                    $el.find('.explanation-container').slideUp(150);
                    renderView();
                } else {
                    alert('Reset error: ' + (resp.error || 'Unknown error'));
                }
            },
            error: function() {
                $btn.prop('disabled', false).text('Try New Attempt');
                alert('Failed to reset question.');
            }
        });
    });

    renderView();
}

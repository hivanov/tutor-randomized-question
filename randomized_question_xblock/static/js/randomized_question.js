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

    function highlightSyntax(code, lang) {
        if (window.hljs && lang && window.hljs.getLanguage(lang)) {
            try {
                return window.hljs.highlight(code, { language: lang }).value;
            } catch (e) {
                // fallback to default escaping
            }
        }
        
        // Simple token coloring fallback for common languages (Python, JS, SQL, Bash)
        var esc = escapeHtml(code);
        // Comments
        esc = esc.replace(/(#[^\n]*|\/\/[^\n]*)/g, '<span class="tok-comment">$1</span>');
        // Strings
        esc = esc.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g, '<span class="tok-string">$1</span>');
        // Numbers
        esc = esc.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tok-number">$1</span>');
        // Keywords
        var keywords = /\b(def|class|return|if|else|elif|for|while|import|from|in|is|not|and|or|None|True|False|self|async|await|const|let|var|function|SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN)\b/g;
        esc = esc.replace(keywords, '<span class="tok-keyword">$1</span>');
        return esc;
    }

    function renderFallbackMath(math, isDisplay) {
        var out = escapeHtml(math);
        // Common LaTeX symbols
        out = out.replace(/\\lfloor\s*/g, '&lfloor;').replace(/\\rfloor\s*/g, '&rfloor;');
        out = out.replace(/\\lceil\s*/g, '&lceil;').replace(/\\rceil\s*/g, '&rceil;');
        out = out.replace(/\\le(q)?\b/g, '&le;').replace(/\\ge(q)?\b/g, '&ge;');
        out = out.replace(/\\ne(q)?\b/g, '&ne;').replace(/\\approx\b/g, '&asymp;');
        out = out.replace(/\\times\b/g, '&times;').replace(/\\cdot\b/g, '&middot;');
        out = out.replace(/\\sum\b/g, '&sum;').replace(/\\prod\b/g, '&prod;').replace(/\\int\b/g, '&int;');
        out = out.replace(/\\infty\b/g, '&infin;');
        out = out.replace(/\\alpha\b/g, '&alpha;').replace(/\\beta\b/g, '&beta;').replace(/\\gamma\b/g, '&gamma;');
        out = out.replace(/\\Omega\b/g, '&Omega;').replace(/\\Theta\b/g, '&Theta;').replace(/\\lambda\b/g, '&lambda;');
        out = out.replace(/\\in\b/g, '&isin;').replace(/\\notin\b/g, '&notin;');
        out = out.replace(/\\log\b/g, '<span class="math-op">log</span>').replace(/\\ln\b/g, '<span class="math-op">ln</span>');
        // Superscripts ^2 or ^{2n}
        out = out.replace(/\^{([^}]+)}/g, '<sup>$1</sup>').replace(/\^([a-zA-Z0-9])/g, '<sup>$1</sup>');
        // Subscripts _i or _{i+1}
        out = out.replace(/_{([^}]+)}/g, '<sub>$1</sub>').replace(/_([a-zA-Z0-9])/g, '<sub>$1</sub>');
        // Fractions \frac{a}{b}
        out = out.replace(/\\frac{([^}]+)}{([^}]+)}/g, '<span class="math-frac"><span class="math-num">$1</span>/<span class="math-den">$2</span></span>');
        // Single letter variables in italics when not already tagged
        out = out.replace(/(^|[^a-zA-Z0-9_&;])([a-zA-Z])(?![a-zA-Z0-9_&;])/g, '$1<em>$2</em>');
        return out;
    }

    function renderMathInString(text) {
        if (!text) return '';

        // 1. Block math $$...$$ or \[...\]
        var processed = text.replace(/\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]/g, function(match, m1, m2) {
            var math = (m1 !== undefined ? m1 : m2).trim();
            if (window.katex && window.katex.renderToString) {
                try {
                    return '<div class="math-display">' + window.katex.renderToString(math, { displayMode: true, throwOnError: false }) + '</div>';
                } catch (e) {
                    // fallback
                }
            }
            return '<div class="math-display">' + renderFallbackMath(math, true) + '</div>';
        });

        // 2. Inline math $...$ or \(...\)
        // Avoid matching escaped dollars \$
        processed = processed.replace(/(^|[^\\])\$([^\$\n]+?)\$|\\\(([\s\S]*?)\\\)/g, function(match, prefix, m1, m2) {
            var math = (m1 !== undefined ? m1 : m2).trim();
            var leading = (m1 !== undefined && prefix) ? prefix : '';
            if (window.katex && window.katex.renderToString) {
                try {
                    return leading + '<span class="math-inline">' + window.katex.renderToString(math, { displayMode: false, throwOnError: false }) + '</span>';
                } catch (e) {
                    // fallback
                }
            }
            return leading + '<span class="math-inline">' + renderFallbackMath(math, false) + '</span>';
        });

        return processed;
    }

    function parseMarkdown(text) {
        if (!text) return '';
        
        // 1. Extract and placeholder code blocks ```lang\ncode\n```
        var codeBlocks = [];
        var processed = text.replace(/```([a-zA-Z0-9_\-]+)?\n([\s\S]*?)```/g, function(match, lang, code) {
            var placeholder = '@@@CODEBLOCK_' + codeBlocks.length + '@@@';
            var highlighted = highlightSyntax(code.trim(), (lang || '').toLowerCase());
            codeBlocks.push(
                '<pre class="code-block' + (lang ? ' language-' + lang : '') + '">' +
                '<code class="code-inner' + (lang ? ' language-' + lang : '') + '">' +
                highlighted +
                '</code></pre>'
            );
            return placeholder;
        });

        // 2. Extract and placeholder inline code `code`
        var inlineCodes = [];
        processed = processed.replace(/`([^`\n]+)`/g, function(match, code) {
            var placeholder = '@@@INLINECODE_' + inlineCodes.length + '@@@';
            inlineCodes.push('<code class="inline-code">' + escapeHtml(code) + '</code>');
            return placeholder;
        });

        // 3. Render math formulas
        processed = renderMathInString(processed);

        // 4. Bold & Italic
        processed = processed
            .replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/__([^_]+)__/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/_([^_]+)_/g, '<em>$1</em>');

        // 5. Line breaks
        processed = processed.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');

        // 6. Restore inline code
        inlineCodes.forEach(function(codeHtml, i) {
            processed = processed.replace('@@@INLINECODE_' + i + '@@@', codeHtml);
        });

        // 7. Restore code blocks
        codeBlocks.forEach(function(blockHtml, i) {
            processed = processed.replace('@@@CODEBLOCK_' + i + '@@@', blockHtml);
        });

        return processed;
    }

    function render(container, rawText) {
        if (!container) return;
        if (!rawText) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = parseMarkdown(rawText);

        // Additional MathJax typesetting hook if MathJax is present
        if (window.MathJax) {
            try {
                if (window.MathJax.typesetPromise) {
                    window.MathJax.typesetPromise([container]).catch(function(e) { /* ignore */ });
                } else if (window.MathJax.Hub && window.MathJax.Hub.Queue) {
                    window.MathJax.Hub.Queue(['Typeset', window.MathJax.Hub, container]);
                }
            } catch (err) {
                // ignore
            }
        }
    }

    return {
        render: render,
        parseMarkdown: parseMarkdown,
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

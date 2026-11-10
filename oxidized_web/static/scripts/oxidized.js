var initDayjs = function() {
  if (typeof dayjs === 'undefined') {
    return false;
  }
  var rawPlugin = window.dayjsPluginUTC || window.dayjs_plugin_utc;
  var utcPlugin = (rawPlugin && typeof rawPlugin.default === 'function') ? rawPlugin.default : rawPlugin;
  if (typeof utcPlugin === 'function' && typeof dayjs.extend === 'function' && !dayjs.utc) {
    try {
      dayjs.extend(utcPlugin);
    } catch (e) {
      console.warn('Failed to extend dayjs with UTC plugin:', e);
    }
  }
  return true;
};

var formatToLocal = function(text, epoch) {
  var rawText = (text !== undefined && text !== null) ? String(text).trim() : '';
  if (!rawText || rawText === 'never' || rawText === 'Never' || rawText === 'unknown' || rawText === '—') {
    return rawText;
  }

  // 1. If Day.js is available
  if (typeof dayjs !== 'undefined') {
    initDayjs();
    var dj;
    if (epoch !== undefined && epoch !== null && epoch !== '') {
      var sec = Number(epoch);
      if (!isNaN(sec) && sec > 0) {
        dj = dayjs.unix(sec);
      }
    }

    if (!dj || !dj.isValid()) {
      var cleaned = rawText.replace(/\s*UTC\s*/gi, '').trim();
      if (typeof dayjs.utc === 'function') {
        dj = dayjs.utc(cleaned);
      } else {
        // Parse with 'Z' appended to treat explicitly as UTC
        var isoLike = cleaned.replace(' ', 'T');
        if (!isoLike.endsWith('Z')) {
          isoLike += 'Z';
        }
        dj = dayjs(isoLike);
      }
    }

    if (dj && dj.isValid()) {
      if (typeof dj.local === 'function') {
        dj = dj.local();
      }
      return dj.format('YYYY-MM-DD HH:mm:ss');
    }
  }

  // 2. Native JavaScript Date fallback if Day.js is unavailable or parsing fails
  try {
    var jsDate;
    if (epoch) {
      jsDate = new Date(Number(epoch) * 1000);
    } else {
      var cleaned = rawText.replace(/\s*UTC\s*/gi, '').trim();
      var isoLike = cleaned.replace(' ', 'T');
      if (!isoLike.endsWith('Z')) {
        isoLike += 'Z';
      }
      jsDate = new Date(isoLike);
    }

    if (jsDate && !isNaN(jsDate.getTime())) {
      var pad = function(n) { return (n < 10 ? '0' : '') + n; };
      return jsDate.getFullYear() + '-' +
        pad(jsDate.getMonth() + 1) + '-' +
        pad(jsDate.getDate()) + ' ' +
        pad(jsDate.getHours()) + ':' +
        pad(jsDate.getMinutes()) + ':' +
        pad(jsDate.getSeconds());
    }
  } catch (e) {
    // Return original text if parsing fails
  }

  return rawText.replace(/\s*UTC\s*/gi, '').trim();
};

var convertTime = function() {
  initDayjs();

  // 1. Elements with .time or explicitly tagged timestamps (excluding option elements)
  $('.time, span[epoch], span[data-epoch], td[epoch], td[data-epoch]').each(function() {
    var rawText = $(this).text().trim();
    if (!rawText || rawText === 'never' || rawText === 'Never' || rawText === 'unknown' || rawText === '—') {
      return;
    }

    var epoch = $(this).attr('data-epoch') || $(this).attr('epoch');
    var converted = formatToLocal(rawText, epoch);
    if (converted) {
      $(this).text(converted);
      try {
        $(this).attr('title', 'Local Time (' + Intl.DateTimeFormat().resolvedOptions().timeZone + ')');
      } catch (e) {}
    }
  });

  // 2. Select option elements containing timestamps (e.g. Compare Revisions dropdowns)
  $('select option').each(function() {
    var optText = $(this).text();
    var match = optText.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\s*UTC)?/);
    if (match) {
      var dateStr = match[1];
      var epoch = $(this).attr('data-epoch') || $(this).attr('epoch');
      var localStr = formatToLocal(dateStr, epoch);
      if (localStr && localStr !== dateStr) {
        var newOptText = optText.replace(match[0], localStr);
        $(this).text(newOptText);
      }
    }
  });
};

$(function() {
  convertTime();

  // Re-run conversion when DataTables redraws or paginates
  $(document).on('draw.dt page.dt order.dt search.dt', function() {
    convertTime();
  });
});

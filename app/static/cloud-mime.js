    // Extension → MIME map. Used so direct URLs are served with the correct Content-Type
    // (objects are sometimes stored as binary/octet-stream, which forces browsers to
    // download them even when the URL is signed with response-content-disposition=inline).
    const MIME_BY_EXT = {
      jpg:'image/jpeg', jpeg:'image/jpeg', png:'image/png', gif:'image/gif', webp:'image/webp',
      svg:'image/svg+xml', bmp:'image/bmp', ico:'image/x-icon', avif:'image/avif', apng:'image/apng',
      jfif:'image/jpeg', jxl:'image/jxl', tif:'image/tiff', tiff:'image/tiff', heic:'image/heic', heif:'image/heif',
      pdf:'application/pdf',
      mp4:'video/mp4', webm:'video/webm', mov:'video/quicktime', mkv:'video/x-matroska', avi:'video/x-msvideo',
      ogv:'video/ogg', m4v:'video/x-m4v', '3gp':'video/3gpp', mpeg:'video/mpeg', mpg:'video/mpeg', wmv:'video/x-ms-wmv', flv:'video/x-flv',
      mp3:'audio/mpeg', wav:'audio/wav', ogg:'audio/ogg', oga:'audio/ogg', opus:'audio/opus', aac:'audio/aac',
      flac:'audio/flac', m4a:'audio/mp4', weba:'audio/webm', aiff:'audio/aiff', aif:'audio/aiff',
      amr:'audio/amr', mid:'audio/midi', midi:'audio/midi',
      txt:'text/plain', md:'text/markdown', markdown:'text/markdown', html:'text/html', htm:'text/html', css:'text/css',
      scss:'text/x-scss', sass:'text/x-sass', less:'text/less',
      js:'text/javascript', mjs:'text/javascript', jsx:'text/jsx', json:'application/json', xml:'application/xml', csv:'text/csv',
      py:'text/x-python', c:'text/x-c', cpp:'text/x-c++src', cc:'text/x-c++src', cxx:'text/x-c++src', h:'text/x-c', hpp:'text/x-c++src',
      java:'text/x-java-source', ts:'text/x-typescript', tsx:'text/x-typescript',
      yml:'text/yaml', yaml:'text/yaml', sh:'text/x-shellscript', bash:'text/x-shellscript', zsh:'text/x-shellscript',
      sql:'text/x-sql', php:'text/x-php', rb:'text/x-ruby', go:'text/x-go', rs:'text/x-rust',
      ini:'text/plain', cfg:'text/plain', conf:'text/plain', env:'text/plain', properties:'text/x-java-properties',
      toml:'text/plain', log:'text/plain', vue:'text/x-vue', svelte:'text/x-svelte',
      dockerfile:'text/plain', gitignore:'text/plain', makefile:'text/x-makefile',
      zip:'application/zip', gz:'application/gzip', tgz:'application/gzip', tar:'application/x-tar',
      '7z':'application/x-7z-compressed', rar:'application/vnd.rar', bz2:'application/x-bzip2',
      xz:'application/x-xz', iso:'application/x-iso9660-image'
    };
    function mimeForKey(key) {
      const ext = (key.split('.').pop() || '').toLowerCase();
      return MIME_BY_EXT[ext] || 'application/octet-stream';
    }


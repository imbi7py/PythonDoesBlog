<%inherit file="feed_base.mako"/>
<%! 
  from datetime import datetime
  import settings 
%>
<%block name="body">
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:sy="http://purl.org/rss/1.0/modules/syndication/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     >
  <channel>
    <title>${settings.BLOG_TITLE}</title>
    <link>${settings.BLOG_URL}</link>
    <description>${settings.BLOG_DESCRIPTION}</description>

    <pubDate>${datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>
    <sy:updatePeriod>hourly</sy:updatePeriod>
    <sy:updateFrequency>1</sy:updateFrequency>

    <generator>PythonDoesBlog</generator>

    % for post in posts:
    <item>
      <title><![CDATA[${post.title}]]></title>
      <link>${post.get_url(absolute=True)}</link>
      <pubDate>${post.pub_date.strftime("%a, %d %b %Y %H:%M:%S %Z")}</pubDate>

      % for tag in post.tags:
      <category><![CDATA[${tag}]]></category>
      % endfor

      <guid>${post.get_url(absolute=True)}</guid>

      <description>${post.title}</description>
      <content:encoded>
	<![CDATA[${self.absolutify(post.get_html(content_only=True, noclasses=True))}]]>
      </content:encoded>
    </item>
    % endfor

  </channel>
</rss>
</%block>
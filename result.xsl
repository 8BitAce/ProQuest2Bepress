<?xml version="1.0" encoding="utf-8"?><!-- DWXMLSource="ProQuest.xml" -->

<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="xml" version="2.0" encoding="UTF-8" indent="yes"/>
<xsl:template match="/">
<documents  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.bepress.com/document-import.xsd">

<xsl:for-each select="DISS_Documents/DISS_submission">
	<document>
	<title><xsl:value-of select="DISS_description/DISS_title"/></title>
  <publication-date><xsl:value-of select="DISS_description/DISS_dates/DISS_comp_date"/>-01-01</publication-date>
  <authors>
  <author xsi:type="individual">
  <email><xsl:value-of select="DISS_authorship/DISS_author/DISS_contact/DISS_email"/></email>
  <institution><xsl:value-of select="DISS_description/DISS_institution/DISS_inst_name"/></institution>
  <lname><xsl:value-of select="DISS_authorship/DISS_author/DISS_name/DISS_surname"/></lname>
  <fname><xsl:value-of select="DISS_authorship/DISS_author/DISS_name/DISS_fname"/></fname>
  <mname><xsl:value-of select="DISS_authorship/DISS_author/DISS_name/DISS_middle"/></mname>
  <suffix><xsl:value-of select="DISS_authorship/DISS_author/DISS_name/DISS_suffix"/></suffix>
  
</author>

</authors>
  <abstract><xsl:value-of select="DISS_content/DISS_abstract"/></abstract>
  
  
  
    <fulltext-url><xsl:value-of select="DISS_content/DISS_binary"/></fulltext-url>

  <document-type><xsl:value-of select="DISS_content/DISS_attachment/DISS_file_category"/></document-type>
  </document>
</xsl:for-each>


</documents>

</xsl:template>

</xsl:stylesheet>